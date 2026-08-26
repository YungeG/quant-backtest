"""Bounded KORU mark/index price-bar capture and exact projection.

Captured provider bytes are authoritative only for their frozen date, hashes, and
availability receipt. Future dates require separately captured hashes and receipts.
Retained observations use the official completed-kline close+1ms policy as
provider-effective availability; later local acquisition never backdates a bar.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import Enum
from zipfile import ZIP_STORED, BadZipFile, ZipFile, ZipInfo

from crypto_quant_domain import (
    InstrumentId,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_sha256,
)
from crypto_quant_market_data import MarketBundleCapability, MarketEvent

from .source_snapshots import (
    RawSourceMember,
    SourceSnapshot,
    SourceSnapshotMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)

_SCHEMA_VERSION = 1
_SYMBOL = "KORUUSDT"
_INTERVAL = "1h"
_INSTRUMENT = InstrumentId(VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual")
_POST_ADJUSTMENT_START_DATE = date(2026, 7, 15)
_EPOCH_DATE = date(1970, 1, 1)
_DAY_NANOSECONDS = 86_400_000_000_000
_HOUR_MILLISECONDS = 3_600_000
_AUTHORIZED_PROJECTION_START = UtcInstant(1_784_109_600_000_000_000)
_ECONOMIC_AVAILABILITY_POLICY_REF = "binance.fapi.completed-kline-close-exclusive.v1"
_MAX_ATTEMPTS = 3
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_INTEGER = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,18})?\Z")
_PRICE = re.compile(r"(?:0|[1-9][0-9]*)(?:\.([0-9]{1,8}))?\Z")
_CSV_HEADER = (
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "count",
    "taker_buy_volume",
    "taker_buy_quote_volume",
    "ignore",
)
_RETAINED_CSV_HEADER = (
    "open_time_utc",
    "open",
    "high",
    "low",
    "close",
    "close_time_utc",
    "volume",
)
_RETAINED_CSV_SCHEMA_IDENTITY = (
    "binance_usdm_koru_price_bars_discovery_bounded_csv_7_column_scale8_v1"
)
_RETAINED_SOURCE_ARTIFACT_TYPE = "binance_fapi_price_bars_raw_csv_v1"
_RETAINED_BASE_MANIFEST_PATH = "research/koruusdt/data/manifest.json"
_RETAINED_SOURCE_MODE = "base_manifest_derived_raw_observations"
_RETAINED_UTC_DATE = "2026-08-24"
_RETAINED_DAY_START_MS = 1_787_529_600_000
_RETAINED_COVERAGE_END_MS = _RETAINED_DAY_START_MS + 11 * _HOUR_MILLISECONDS
_RETAINED_ORIGINAL_REQUEST_START_MS = 1_782_136_500_000
_RETAINED_ORIGINAL_REQUEST_END_EXCLUSIVE_MS = 1_787_569_200_000
_RETAINED_PARAMETER_LIMIT = 1000
_RETAINED_BASE_MANIFEST_MEMBER_KEY = "retained/base/manifest.json"
_RETAINED_DERIVED_CSV_MEMBER_KEY = "derived/KORUUSDT-1h-2026-08-24.discovery-bounded.csv"
_PHASE = TimelinePhase(0, "market_data")
_POINT_CAPABILITY = MarketBundleCapability("price.point", 1)
_BAR_CAPABILITY = MarketBundleCapability("price.bar", 1)
_UNKNOWN_PREFIX_GAP_CLASSIFICATION = "unknown_unproven"
_AUTHORITY_PREFIX_CLASSIFICATION = (
    "corporate_action_excluded_before_2026-07-15T10:00:00Z"
)
_SUFFIX_GAP_CLASSIFICATION = "unknown_unproven"
_INTERNAL_GAP_CLASSIFICATION = "none_observed_by_contiguous_hours"
_COMMON_PAYLOAD_KEYS = frozenset(
    {
        "source_kind",
        "price_purpose",
        "interval",
        "open_time_milliseconds",
        "close_time_milliseconds",
        "open_units",
        "high_units",
        "low_units",
        "close_units",
        "price_scale",
        "source_record_hash",
        "request_hash",
        "capture_hash",
        "source_snapshot_id",
        "source_snapshot_hash",
        "source_provenance_hash",
        "source_member_key",
        "source_member_hash",
        "archive_member_key",
        "archive_member_hash",
        "checksum_member_key",
        "checksum_member_hash",
        "economic_availability_policy_ref",
        "archive_available_at_epoch_nanoseconds",
        "acquired_at_epoch_nanoseconds",
    }
)

FetchBytes = Callable[[str], tuple[int, bytes]]


class BinanceUsdmKoruPriceBarsSourceKindV1(str, Enum):
    MARK_PRICE = "mark_price"
    INDEX_PRICE = "index_price"


_RETAINED_ENDPOINTS = {
    BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE: (
        "https://fapi.binance.com/fapi/v1/markPriceKlines"
    ),
    BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE: (
        "https://fapi.binance.com/fapi/v1/indexPriceKlines"
    ),
}
_RETAINED_SOURCE_IDS = {
    BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE: (
        "binance_futures_mark_price_kline"
    ),
    BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE: (
        "binance_futures_index_price_kline"
    ),
}
_RETAINED_SOURCE_PATHS = {
    BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE: (
        "research/koruusdt/data/binance_mark_raw.csv"
    ),
    BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE: (
        "research/koruusdt/data/binance_index_raw.csv"
    ),
}
_RETAINED_SOURCE_SHA256 = {
    BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE: (
        "sha256:e46fd0296dea518616fa11905db3a07e6d8ab672d9867298f88be12e771918d4"
    ),
    BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE: (
        "sha256:a67e4be307cf2701b0c16b76a193129907e86bc4b7294b52ce11b304ce278046"
    ),
}
_RETAINED_BASE_MANIFEST_FILE_SHA256 = (
    "sha256:c20ab7e8444e4f2a60e6e2b10e9faf57345e68c6cd10a4682c744f3fe4f91a80"
)
_RETAINED_BASE_MANIFEST_IDENTITY = (
    "sha256:066c775e60ba402b631b406fd8138da200d7e30a136e0efb7c2c13b196680d64"
)


@dataclass(frozen=True, slots=True)
class _SourceDefinition:
    archive_directory: str
    source_key_part: str


_SOURCE_DEFINITIONS = {
    BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE: _SourceDefinition(
        "markPriceKlines", "mark_price_klines"
    ),
    BinanceUsdmKoruPriceBarsSourceKindV1.INDEX_PRICE: _SourceDefinition(
        "indexPriceKlines", "index_price_klines"
    ),
}


@dataclass(frozen=True, slots=True)
class _EventDefinition:
    price_purpose: str
    stream_key: str
    event_type: str
    capability: MarketBundleCapability
    point: bool


_MARK_EVENT_DEFINITIONS = (
    _EventDefinition(
        "strategy",
        "binance_usdm.mark_price.strategy.koruusdt.1h.v1",
        "binance_usdm_koru_mark_price_strategy_bar_v1",
        _BAR_CAPABILITY,
        False,
    ),
    _EventDefinition(
        "valuation",
        "binance_usdm.mark_price.valuation.koruusdt.1h.v1",
        "binance_usdm_koru_mark_price_point_v1",
        _POINT_CAPABILITY,
        True,
    ),
    _EventDefinition(
        "margin",
        "binance_usdm.mark_price.margin.koruusdt.1h.v1",
        "binance_usdm_koru_mark_price_point_v1",
        _POINT_CAPABILITY,
        True,
    ),
    _EventDefinition(
        "liquidation",
        "binance_usdm.mark_price.liquidation.koruusdt.1h.v1",
        "binance_usdm_koru_mark_price_liquidation_bar_v1",
        _BAR_CAPABILITY,
        False,
    ),
)
_INDEX_EVENT_DEFINITIONS = (
    _EventDefinition(
        "strategy",
        "binance_usdm.index_price.strategy.koruusdt.1h.v1",
        "binance_usdm_koru_index_price_strategy_bar_v1",
        _BAR_CAPABILITY,
        False,
    ),
)


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _archive_name(utc_date: str) -> str:
    return f"{_SYMBOL}-{_INTERVAL}-{utc_date}.zip"


def _checksum_name(utc_date: str) -> str:
    return _archive_name(utc_date) + ".CHECKSUM"


def _csv_name(utc_date: str) -> str:
    return f"{_SYMBOL}-{_INTERVAL}-{utc_date}.csv"


def _date_value(value: object) -> date:
    if type(value) is not str:
        raise ValueError("utc_date must be an exact ISO UTC date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("utc_date must be an exact ISO UTC date") from error
    if parsed.isoformat() != value or parsed < _POST_ADJUSTMENT_START_DATE:
        raise ValueError("utc_date must be on or after 2026-07-15")
    return parsed


def _date_bounds(utc_date: str) -> tuple[UtcInstant, UtcInstant]:
    day = _date_value(utc_date)
    start = (day - _EPOCH_DATE).days * _DAY_NANOSECONDS
    return UtcInstant(start), UtcInstant(start + _DAY_NANOSECONDS)


def _content_hash(name: str, value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 digest")
    return value


def _source_definition(
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
) -> _SourceDefinition:
    return _SOURCE_DEFINITIONS[source_kind]


def _base_url(source_kind: BinanceUsdmKoruPriceBarsSourceKindV1) -> str:
    directory = _source_definition(source_kind).archive_directory
    return (
        "https://data.binance.vision/data/futures/um/daily/"
        f"{directory}/{_SYMBOL}/{_INTERVAL}/"
    )


def _source_key(
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
    utc_date: str,
    archive_available_at_epoch_nanoseconds: int,
) -> str:
    part = _source_definition(source_kind).source_key_part
    return (
        f"binance.public_data.futures.um.daily.{part}.koruusdt.1h.{utc_date}."
        f"economic-policy-{_ECONOMIC_AVAILABILITY_POLICY_REF}."
        f"archive-available-at-{archive_available_at_epoch_nanoseconds}"
    )


def _retained_parameters(
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
) -> dict[str, object]:
    instrument_parameter = (
        "symbol"
        if source_kind is BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE
        else "pair"
    )
    return {
        "endTime": _RETAINED_ORIGINAL_REQUEST_END_EXCLUSIVE_MS - 1,
        "interval": _INTERVAL,
        "limit": _RETAINED_PARAMETER_LIMIT,
        "startTime": _RETAINED_ORIGINAL_REQUEST_START_MS,
        instrument_parameter: _SYMBOL,
    }


def _retained_parameter_hash(
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
) -> str:
    return canonical_sha256(_retained_parameters(source_kind))


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruRetainedPriceBarsAuthorityV1:
    source_artifact_type: str
    source_artifact_path: str
    source_artifact_sha256: str
    source_acquired_at_epoch_nanoseconds: int
    base_manifest_path: str
    base_manifest_file_sha256: str
    base_manifest_identity: str
    original_binance_endpoint: str
    original_binance_parameter_sha256: str
    original_request_start: UtcInstant
    original_request_end_exclusive: UtcInstant
    provider_availability_authority_ref: str
    selected_coverage_start: UtcInstant
    selected_coverage_end_exclusive: UtcInstant
    derived_csv_member_name: str
    derived_csv_sha256: str
    derived_csv_schema_identity: str
    development_only: bool = True
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if self.source_artifact_type != _RETAINED_SOURCE_ARTIFACT_TYPE:
            raise ValueError("source artifact type must be exact")
        _content_hash("source_artifact_sha256", self.source_artifact_sha256)
        if (
            type(self.source_acquired_at_epoch_nanoseconds) is not int
            or self.source_acquired_at_epoch_nanoseconds <= 0
        ):
            raise ValueError("source acquisition must be an exact positive UTC instant")
        if self.base_manifest_path != _RETAINED_BASE_MANIFEST_PATH:
            raise ValueError("base manifest path must be exact")
        _content_hash("base_manifest_file_sha256", self.base_manifest_file_sha256)
        _content_hash("base_manifest_identity", self.base_manifest_identity)
        if self.original_binance_endpoint not in _RETAINED_ENDPOINTS.values():
            raise ValueError("original_binance_endpoint must be an exact KORU endpoint")
        source_kind = next(
            kind
            for kind, endpoint in _RETAINED_ENDPOINTS.items()
            if endpoint == self.original_binance_endpoint
        )
        if self.source_artifact_path != _RETAINED_SOURCE_PATHS[source_kind]:
            raise ValueError("source artifact path must match the exact endpoint kind")
        _content_hash(
            "original_binance_parameter_sha256",
            self.original_binance_parameter_sha256,
        )
        if self.original_binance_parameter_sha256 != _retained_parameter_hash(
            source_kind
        ):
            raise ValueError("original Binance parameters must be exact")
        if (
            type(self.original_request_start) is not UtcInstant
            or type(self.original_request_end_exclusive) is not UtcInstant
            or self.original_request_start.epoch_nanoseconds
            != _RETAINED_ORIGINAL_REQUEST_START_MS * 1_000_000
            or self.original_request_end_exclusive.epoch_nanoseconds
            != _RETAINED_ORIGINAL_REQUEST_END_EXCLUSIVE_MS * 1_000_000
        ):
            raise ValueError("original request must retain exact Jun22-Aug24 window")
        if (
            self.provider_availability_authority_ref
            != _ECONOMIC_AVAILABILITY_POLICY_REF
        ):
            raise ValueError("provider availability authority ref must be exact")
        if (
            type(self.selected_coverage_start) is not UtcInstant
            or type(self.selected_coverage_end_exclusive) is not UtcInstant
        ):
            raise TypeError("selected coverage must use exact UTC instants")
        start_ms = self.selected_coverage_start.epoch_nanoseconds // 1_000_000
        end_ms = self.selected_coverage_end_exclusive.epoch_nanoseconds // 1_000_000
        if (
            self.selected_coverage_start.epoch_nanoseconds % 1_000_000 != 0
            or self.selected_coverage_end_exclusive.epoch_nanoseconds % 1_000_000 != 0
            or start_ms != _RETAINED_DAY_START_MS
            or end_ms != _RETAINED_COVERAGE_END_MS
        ):
            raise ValueError("selected coverage must be exact Aug24 [00:00,11:00) UTC")
        if (
            type(self.derived_csv_member_name) is not str
            or self.derived_csv_member_name
            != f"{_SYMBOL}-{_INTERVAL}-{_RETAINED_UTC_DATE}.discovery-bounded.csv"
        ):
            raise ValueError("derived CSV member name must be exact")
        _content_hash("derived_csv_sha256", self.derived_csv_sha256)
        if self.derived_csv_schema_identity != _RETAINED_CSV_SCHEMA_IDENTITY:
            raise ValueError("derived CSV schema identity must be exact")
        if (
            type(self.development_only) is not bool
            or not self.development_only
            or type(self.decision_grade_eligible) is not bool
            or self.decision_grade_eligible
            or type(self.deployment_authorized) is not bool
            or self.deployment_authorized
        ):
            raise ValueError("retained authority must remain development-only")

    @property
    def authority_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_retained_price_bars_authority_v1",
            "schema_version": _SCHEMA_VERSION,
            "source_artifact_type": self.source_artifact_type,
            "source_artifact_path": self.source_artifact_path,
            "source_artifact_sha256": self.source_artifact_sha256,
            "source_acquired_at_epoch_nanoseconds": self.source_acquired_at_epoch_nanoseconds,
            "base_manifest_path": self.base_manifest_path,
            "base_manifest_file_sha256": self.base_manifest_file_sha256,
            "base_manifest_identity": self.base_manifest_identity,
            "original_binance_endpoint": self.original_binance_endpoint,
            "original_binance_parameter_sha256": self.original_binance_parameter_sha256,
            "original_request_start": self.original_request_start.to_canonical_dict(),
            "original_request_end_exclusive": self.original_request_end_exclusive.to_canonical_dict(),
            "provider_availability_authority_ref": self.provider_availability_authority_ref,
            "selected_coverage_start": self.selected_coverage_start.to_canonical_dict(),
            "selected_coverage_end_exclusive": self.selected_coverage_end_exclusive.to_canonical_dict(),
            "derived_csv_member_name": self.derived_csv_member_name,
            "derived_csv_sha256": self.derived_csv_sha256,
            "derived_csv_schema_identity": self.derived_csv_schema_identity,
            "development_only": self.development_only,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


def _trusted_authority(
    value: object,
) -> BinanceUsdmKoruRetainedPriceBarsAuthorityV1 | None:
    if type(value) is not BinanceUsdmKoruRetainedPriceBarsAuthorityV1:
        return None
    try:
        rebuilt = BinanceUsdmKoruRetainedPriceBarsAuthorityV1(
            source_artifact_type=value.source_artifact_type,
            source_artifact_path=value.source_artifact_path,
            source_artifact_sha256=value.source_artifact_sha256,
            source_acquired_at_epoch_nanoseconds=value.source_acquired_at_epoch_nanoseconds,
            base_manifest_path=value.base_manifest_path,
            base_manifest_file_sha256=value.base_manifest_file_sha256,
            base_manifest_identity=value.base_manifest_identity,
            original_binance_endpoint=value.original_binance_endpoint,
            original_binance_parameter_sha256=value.original_binance_parameter_sha256,
            original_request_start=value.original_request_start,
            original_request_end_exclusive=value.original_request_end_exclusive,
            provider_availability_authority_ref=value.provider_availability_authority_ref,
            selected_coverage_start=value.selected_coverage_start,
            selected_coverage_end_exclusive=value.selected_coverage_end_exclusive,
            derived_csv_member_name=value.derived_csv_member_name,
            derived_csv_sha256=value.derived_csv_sha256,
            derived_csv_schema_identity=value.derived_csv_schema_identity,
            development_only=value.development_only,
            decision_grade_eligible=value.decision_grade_eligible,
            deployment_authorized=value.deployment_authorized,
        )
        if rebuilt.to_canonical_dict() != value.to_canonical_dict():
            return None
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt


def build_binance_usdm_koru_price_bars_retained_observations_evidence_v1(
    authority: BinanceUsdmKoruRetainedPriceBarsAuthorityV1,
    csv_bytes: bytes,
) -> tuple[bytes, bytes]:
    trusted = _trusted_authority(authority)
    if (
        trusted is None
        or type(csv_bytes) is not bytes
        or _sha256(csv_bytes) != trusted.derived_csv_sha256
    ):
        raise ValueError("derived CSV must exactly match retained authority")
    output = io.BytesIO()
    member = ZipInfo(trusted.derived_csv_member_name, (2026, 8, 24, 0, 0, 0))
    member.compress_type = ZIP_STORED
    member.external_attr = 0o644 << 16
    with ZipFile(output, "w") as archive:
        archive.writestr(member, csv_bytes)
    archive_bytes = output.getvalue()
    checksum_bytes = (
        f"{_sha256(archive_bytes)[7:]}  {_archive_name(_RETAINED_UTC_DATE)}\n".encode()
    )
    return archive_bytes, checksum_bytes


def _json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _manifest_sha256(manifest: dict[str, object]) -> str:
    hashable = dict(manifest)
    hashable["manifest_sha256"] = ""
    return _sha256(
        json.dumps(
            hashable,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
    )


def _base_manifest(base_manifest_bytes: bytes) -> dict[str, object]:
    if type(base_manifest_bytes) is not bytes:
        raise ValueError("base manifest must be exact bytes")
    try:
        value = json.loads(base_manifest_bytes, object_pairs_hook=_json_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("base manifest must be exact JSON") from error
    if type(value) is not dict:
        raise ValueError("base manifest must be a JSON object")
    manifest = value
    declared = manifest.get("manifest_sha256")
    if type(declared) is not str or declared != _manifest_sha256(manifest):
        raise ValueError("base manifest canonical hash mismatch")
    return manifest


def _exact_mapping(value: object, expected: dict[str, object]) -> bool:
    return type(value) is dict and value == expected


def _manifest_source(
    manifest: dict[str, object],
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
) -> dict[str, object]:
    sources = manifest.get("sources")
    if type(sources) is not list:
        raise ValueError("base manifest sources missing")
    matches = [
        source
        for source in sources
        if type(source) is dict
        and source.get("source_id") == _RETAINED_SOURCE_IDS[source_kind]
    ]
    if len(matches) != 1:
        raise ValueError("base manifest source must be unique")
    source = matches[0]
    if (
        source.get("endpoint") != _RETAINED_ENDPOINTS[source_kind]
        or not _exact_mapping(
            source.get("parameters"), _retained_parameters(source_kind)
        )
        or source.get("type") != "BINANCE_KLINES"
        or source.get("end_semantics")
        != "endTime is inclusive at the endpoint; requested end is exclusive, so endTime=end_ms-1"
    ):
        raise ValueError("base manifest source request mismatch")
    return source


def _manifest_artifact_hash(
    manifest: dict[str, object], source_kind: BinanceUsdmKoruPriceBarsSourceKindV1
) -> str:
    artifacts = manifest.get("artifacts")
    artifact_name = _RETAINED_SOURCE_PATHS[source_kind].rsplit("/", 1)[-1]
    if type(artifacts) is not list:
        raise ValueError("base manifest artifacts missing")
    matches = [
        artifact
        for artifact in artifacts
        if type(artifact) is dict and artifact.get("path") == artifact_name
    ]
    if len(matches) != 1 or type(matches[0].get("sha256")) is not str:
        raise ValueError("base manifest artifact must be unique")
    return _content_hash("source artifact sha256", matches[0]["sha256"])


def _derived_subset_from_source(source_csv_bytes: bytes) -> bytes:
    if (
        type(source_csv_bytes) is not bytes
        or b"\r" in source_csv_bytes
        or not source_csv_bytes.endswith(b"\n")
    ):
        raise ValueError("source CSV encoding mismatch")
    lines = source_csv_bytes.splitlines(keepends=True)
    header = (",".join(_RETAINED_CSV_HEADER) + "\n").encode()
    if not lines or lines[0] != header:
        raise ValueError("source CSV header mismatch")
    prefix = (_RETAINED_UTC_DATE + "T").encode()
    selected = tuple(line for line in lines[1:] if line.startswith(prefix))
    derived = header + b"".join(selected)
    rows = _validated_rows(
        _csv_rows(derived, _RETAINED_CSV_HEADER),
        UtcInstant(_RETAINED_DAY_START_MS * 1_000_000),
        UtcInstant(_RETAINED_COVERAGE_END_MS * 1_000_000),
        retained=True,
    )
    if len(rows) != 11:
        raise ValueError("selected Aug24 source subset mismatch")
    return derived


def _reconstruct_retained_authority(
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
    source_csv_bytes: bytes,
    base_manifest_bytes: bytes,
    derived_csv_bytes: bytes,
    archive_bytes: bytes,
    checksum_bytes: bytes,
) -> BinanceUsdmKoruRetainedPriceBarsAuthorityV1:
    if any(
        type(value) is not bytes
        for value in (
            source_csv_bytes,
            base_manifest_bytes,
            derived_csv_bytes,
            archive_bytes,
            checksum_bytes,
        )
    ):
        raise ValueError("retained evidence must be exact bytes")
    if _sha256(base_manifest_bytes) != _RETAINED_BASE_MANIFEST_FILE_SHA256:
        raise ValueError("base manifest frozen file hash mismatch")
    manifest = _base_manifest(base_manifest_bytes)
    if manifest.get("manifest_sha256") != _RETAINED_BASE_MANIFEST_IDENTITY:
        raise ValueError("base manifest frozen identity mismatch")
    if not _exact_mapping(
        manifest.get("requested_window"),
        {
            "end_ms_exclusive": _RETAINED_ORIGINAL_REQUEST_END_EXCLUSIVE_MS,
            "end_utc_exclusive": "2026-08-24T11:00:00.000Z",
            "interval": _INTERVAL,
            "start_ms": _RETAINED_ORIGINAL_REQUEST_START_MS,
            "start_utc_inclusive": "2026-06-22T13:55:00.000Z",
        },
    ):
        raise ValueError("base manifest original request window mismatch")
    manifest_identity = manifest.get("manifest_sha256")
    if type(manifest_identity) is not str:
        raise ValueError("base manifest identity missing")
    artifact_hash = _manifest_artifact_hash(manifest, source_kind)
    if (
        artifact_hash != _RETAINED_SOURCE_SHA256[source_kind]
        or _sha256(source_csv_bytes) != artifact_hash
    ):
        raise ValueError("source artifact bytes mismatch")
    source = _manifest_source(manifest, source_kind)
    acquired_text = source.get("as_of_utc")
    if type(acquired_text) is not str:
        raise ValueError("source acquisition missing")
    source_acquired_at = _iso_milliseconds(acquired_text) * 1_000_000
    expected_derived = _derived_subset_from_source(source_csv_bytes)
    if derived_csv_bytes != expected_derived:
        raise ValueError("derived CSV is not the byte-exact Aug24 source subset")
    authority = BinanceUsdmKoruRetainedPriceBarsAuthorityV1(
        source_artifact_type=_RETAINED_SOURCE_ARTIFACT_TYPE,
        source_artifact_path=_RETAINED_SOURCE_PATHS[source_kind],
        source_artifact_sha256=artifact_hash,
        source_acquired_at_epoch_nanoseconds=source_acquired_at,
        base_manifest_path=_RETAINED_BASE_MANIFEST_PATH,
        base_manifest_file_sha256=_sha256(base_manifest_bytes),
        base_manifest_identity=manifest_identity,
        original_binance_endpoint=_RETAINED_ENDPOINTS[source_kind],
        original_binance_parameter_sha256=_retained_parameter_hash(source_kind),
        original_request_start=UtcInstant(
            _RETAINED_ORIGINAL_REQUEST_START_MS * 1_000_000
        ),
        original_request_end_exclusive=UtcInstant(
            _RETAINED_ORIGINAL_REQUEST_END_EXCLUSIVE_MS * 1_000_000
        ),
        provider_availability_authority_ref=_ECONOMIC_AVAILABILITY_POLICY_REF,
        selected_coverage_start=UtcInstant(_RETAINED_DAY_START_MS * 1_000_000),
        selected_coverage_end_exclusive=UtcInstant(
            _RETAINED_COVERAGE_END_MS * 1_000_000
        ),
        derived_csv_member_name=_RETAINED_DERIVED_CSV_MEMBER_KEY.split("/", 1)[1],
        derived_csv_sha256=_sha256(derived_csv_bytes),
        derived_csv_schema_identity=_RETAINED_CSV_SCHEMA_IDENTITY,
    )
    expected_archive, expected_checksum = (
        build_binance_usdm_koru_price_bars_retained_observations_evidence_v1(
            authority, derived_csv_bytes
        )
    )
    if archive_bytes != expected_archive or checksum_bytes != expected_checksum:
        raise ValueError("derived ZIP/checksum must be deterministic")
    return authority


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruPriceBarsSourceBoundedRequestV1:
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1
    instrument_id: InstrumentId
    interval: str
    utc_date: str
    archive_available_at_epoch_nanoseconds: int
    acquired_at_epoch_nanoseconds: int
    expected_archive_sha256: str
    expected_checksum_sha256: str
    authority: BinanceUsdmKoruRetainedPriceBarsAuthorityV1 | None = None

    def __post_init__(self) -> None:
        if type(self.source_kind) is not BinanceUsdmKoruPriceBarsSourceKindV1:
            raise ValueError("source_kind must be exact MARK_PRICE or INDEX_PRICE")
        if (
            type(self.instrument_id) is not InstrumentId
            or self.instrument_id != _INSTRUMENT
        ):
            raise ValueError("instrument_id must be the exact KORU tradifi perpetual")
        if type(self.interval) is not str or self.interval != _INTERVAL:
            raise ValueError("interval must be exactly 1h")
        _, day_end = _date_bounds(self.utc_date)
        if type(self.archive_available_at_epoch_nanoseconds) is not int:
            raise ValueError("archive_available_at must be an exact UTC instant")
        if type(self.acquired_at_epoch_nanoseconds) is not int:
            raise ValueError("acquired_at must be an exact UTC instant")
        archive_available_at = UtcInstant(self.archive_available_at_epoch_nanoseconds)
        acquired_at = UtcInstant(self.acquired_at_epoch_nanoseconds)
        if archive_available_at < day_end:
            raise ValueError(
                "archive_available_at cannot precede requested UTC day end"
            )
        if acquired_at < archive_available_at:
            raise ValueError("acquired_at cannot precede archive_available_at")
        _ = _content_hash("expected_archive_sha256", self.expected_archive_sha256)
        _ = _content_hash("expected_checksum_sha256", self.expected_checksum_sha256)
        if self.authority is not None:
            authority = _trusted_authority(self.authority)
            if (
                authority is None
                or self.utc_date != _RETAINED_UTC_DATE
                or authority.original_binance_endpoint
                != _RETAINED_ENDPOINTS[self.source_kind]
                or authority.original_binance_parameter_sha256
                != _retained_parameter_hash(self.source_kind)
                or authority.provider_availability_authority_ref
                != _ECONOMIC_AVAILABILITY_POLICY_REF
                or self.archive_available_at_epoch_nanoseconds
                < authority.source_acquired_at_epoch_nanoseconds
                or self.acquired_at_epoch_nanoseconds
                < authority.source_acquired_at_epoch_nanoseconds
            ):
                raise ValueError("retained request authority does not exactly bind Aug24")

    @property
    def symbol(self) -> str:
        return _SYMBOL

    @property
    def archive_name(self) -> str:
        return _archive_name(self.utc_date)

    @property
    def checksum_name(self) -> str:
        return _checksum_name(self.utc_date)

    @property
    def csv_name(self) -> str:
        if self.authority is not None:
            return self.authority.derived_csv_member_name
        return _csv_name(self.utc_date)

    @property
    def urls(self) -> tuple[str, str]:
        if self.authority is not None:
            raise ValueError("retained observations do not claim provider archive URLs")
        base_url = _base_url(self.source_kind)
        return (base_url + self.archive_name, base_url + self.checksum_name)

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        if self.authority is None:
            archive_url, checksum_url = self.urls
            return {
                "type": "binance_usdm_koru_price_bars_source_bounded_request_v1",
                "schema_version": _SCHEMA_VERSION,
                "source_kind": self.source_kind.value,
                "instrument_id": self.instrument_id.to_canonical_dict(),
                "symbol": _SYMBOL,
                "interval": self.interval,
                "utc_date": self.utc_date,
                "archive_url": archive_url,
                "checksum_url": checksum_url,
                "archive_available_at_epoch_nanoseconds": self.archive_available_at_epoch_nanoseconds,
                "acquired_at_epoch_nanoseconds": self.acquired_at_epoch_nanoseconds,
                "expected_archive_sha256": self.expected_archive_sha256,
                "expected_checksum_sha256": self.expected_checksum_sha256,
            }
        return {
            "type": "binance_usdm_koru_price_bars_source_bounded_request_v1",
            "schema_version": _SCHEMA_VERSION,
            "source_kind": self.source_kind.value,
            "instrument_id": self.instrument_id.to_canonical_dict(),
            "symbol": _SYMBOL,
            "interval": self.interval,
            "utc_date": self.utc_date,
            "source_mode": _RETAINED_SOURCE_MODE,
            "authority": self.authority.to_canonical_dict(),
            "authority_hash": self.authority.authority_hash,
            "archive_available_at_epoch_nanoseconds": self.archive_available_at_epoch_nanoseconds,
            "acquired_at_epoch_nanoseconds": self.acquired_at_epoch_nanoseconds,
            "expected_archive_sha256": self.expected_archive_sha256,
            "expected_checksum_sha256": self.expected_checksum_sha256,
        }


def _trusted_request(
    value: object,
) -> BinanceUsdmKoruPriceBarsSourceBoundedRequestV1 | None:
    if type(value) is not BinanceUsdmKoruPriceBarsSourceBoundedRequestV1:
        return None
    try:
        rebuilt = BinanceUsdmKoruPriceBarsSourceBoundedRequestV1(
            value.source_kind,
            value.instrument_id,
            value.interval,
            value.utc_date,
            value.archive_available_at_epoch_nanoseconds,
            value.acquired_at_epoch_nanoseconds,
            value.expected_archive_sha256,
            value.expected_checksum_sha256,
            value.authority,
        )
        if rebuilt.to_canonical_dict() != value.to_canonical_dict():
            return None
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return rebuilt


def _provenance(
    request: BinanceUsdmKoruPriceBarsSourceBoundedRequestV1,
) -> SourceSnapshotProvenance:
    if request.authority is not None:
        return SourceSnapshotProvenance(
            vendor_key="repository.retained_binance_observations",
            source_key=(
                "binance.fapi.base-manifest-derived.koruusdt.1h.2026-08-24."
                + request.source_kind.value
                + ".authority-"
                + request.authority.authority_hash[7:]
            ),
            license_ref="binance.api.terms",
            retention_policy_ref="development.retained-observation-authority.v1",
        )
    return SourceSnapshotProvenance(
        vendor_key="binance.public_data",
        source_key=_source_key(
            request.source_kind,
            request.utc_date,
            request.archive_available_at_epoch_nanoseconds,
        ),
        license_ref="binance.public_data.terms",
        retention_policy_ref="backtest.fixture.retention",
    )


class BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1(str, Enum):
    CONFIGURATION_INVALID = "configuration_invalid"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    AUTHENTICATION_REJECTED = "authentication_rejected"
    RATE_LIMIT_EXHAUSTED = "rate_limit_exhausted"
    DATA_GAP_DETECTED = "data_gap_detected"
    SOURCE_SCHEMA_MISMATCH = "source_schema_mismatch"
    SOURCE_HASH_MISMATCH = "source_hash_mismatch"
    SNAPSHOT_INVALID = "snapshot_invalid"
    NORMALIZATION_FAILED = "normalization_failed"
    DUPLICATE_OR_CONFLICT = "duplicate_or_conflict"
    ORDER_VIOLATION = "order_violation"


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruPriceBarsSourceBoundedFailureV1:
    code: BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1
    subject: str | None = None
    row_number: int | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1:
            raise TypeError("code must be an exact KORU price-bar failure code")
        if self.subject is not None and (
            type(self.subject) is not str
            or not self.subject
            or self.subject != self.subject.strip()
        ):
            raise ValueError("subject must be canonical text or None")
        if self.row_number is not None and (
            type(self.row_number) is not int or self.row_number <= 0
        ):
            raise ValueError("row_number must be a positive integer or None")

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_price_bars_source_bounded_failure_v1",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
            "row_number": self.row_number,
        }


def _failure(
    code: BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1,
    subject: str | None = None,
    row_number: int | None = None,
) -> BinanceUsdmKoruPriceBarsSourceBoundedFailureV1:
    return BinanceUsdmKoruPriceBarsSourceBoundedFailureV1(code, subject, row_number)


def _member_prefix(
    request: BinanceUsdmKoruPriceBarsSourceBoundedRequestV1,
) -> str:
    return "derived/" if request.authority is not None else "archive/"


def _retained_member_keys(
    request: BinanceUsdmKoruPriceBarsSourceBoundedRequestV1,
) -> tuple[str, ...]:
    authority = request.authority
    if authority is None:
        raise ValueError("retained authority required")
    return tuple(
        sorted(
            (
                _RETAINED_BASE_MANIFEST_MEMBER_KEY,
                "retained/source/" + authority.source_artifact_path.rsplit("/", 1)[-1],
                _RETAINED_DERIVED_CSV_MEMBER_KEY,
                "derived/" + request.archive_name,
                "derived/" + request.checksum_name,
            )
        )
    )


def _snapshot_member(
    snapshot: SourceSnapshot, member_key: str
) -> SourceSnapshotMember:
    return next(member for member in snapshot.members if member.member_key == member_key)


def _snapshot_matches_request(
    request: BinanceUsdmKoruPriceBarsSourceBoundedRequestV1,
    snapshot: SourceSnapshot,
) -> bool:
    archive_key = _member_prefix(request) + request.archive_name
    checksum_key = _member_prefix(request) + request.checksum_name
    expected_keys = (
        _retained_member_keys(request)
        if request.authority is not None
        else (archive_key, checksum_key)
    )
    if (
        type(snapshot) is not SourceSnapshot
        or verify_source_snapshot(snapshot).snapshot is None
        or tuple(member.member_key for member in snapshot.members) != expected_keys
        or snapshot.provenance != _provenance(request)
        or snapshot.decision_grade_eligible
        or snapshot.deployment_authorized
    ):
        return False
    if any(
        member.acquired_at_epoch_nanoseconds != request.acquired_at_epoch_nanoseconds
        or member.mode != "0644"
        or member.content_hash != member.declared_sha256
        for member in snapshot.members
    ):
        return False
    try:
        archive = snapshot.member_bytes(archive_key)
        checksum = snapshot.member_bytes(checksum_key)
    except ValueError:
        return False
    if not (
        _sha256(archive) == request.expected_archive_sha256
        and _sha256(checksum) == request.expected_checksum_sha256
        and checksum
        == f"{request.expected_archive_sha256[7:]}  {request.archive_name}\n".encode()
    ):
        return False
    if request.authority is None:
        return True
    try:
        source_key = "retained/source/" + request.authority.source_artifact_path.rsplit(
            "/", 1
        )[-1]
        reconstructed = _reconstruct_retained_authority(
            request.source_kind,
            snapshot.member_bytes(source_key),
            snapshot.member_bytes(_RETAINED_BASE_MANIFEST_MEMBER_KEY),
            snapshot.member_bytes(_RETAINED_DERIVED_CSV_MEMBER_KEY),
            archive,
            checksum,
        )
        return reconstructed.to_canonical_dict() == request.authority.to_canonical_dict()
    except (BadZipFile, KeyError, OSError, RuntimeError, StopIteration, ValueError):
        return False


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1:
    request: BinanceUsdmKoruPriceBarsSourceBoundedRequestV1
    snapshot: SourceSnapshot
    archive_attempts: int
    checksum_attempts: int
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        trusted = _trusted_request(self.request)
        if (
            trusted is None
            or type(self.archive_attempts) is not int
            or not 1 <= self.archive_attempts <= _MAX_ATTEMPTS
            or type(self.checksum_attempts) is not int
            or not 1 <= self.checksum_attempts <= _MAX_ATTEMPTS
            or not _snapshot_matches_request(trusted, self.snapshot)
        ):
            raise ValueError("capture result must bind exact verified KORU price bars")
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("development-only qualification flags must remain false")

    @property
    def capture_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_price_bars_source_bounded_capture_result_v1",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request.to_canonical_dict(),
            "request_hash": self.request.request_hash,
            "snapshot": self.snapshot.to_canonical_dict(),
            "source_snapshot_hash": canonical_sha256(self.snapshot.to_canonical_dict()),
            "archive_attempts": self.archive_attempts,
            "checksum_attempts": self.checksum_attempts,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


def _trusted_capture(
    value: object,
) -> BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1 | None:
    if type(value) is not BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1:
        return None
    try:
        rebuilt = BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1(
            value.request,
            value.snapshot,
            value.archive_attempts,
            value.checksum_attempts,
            value.decision_grade_eligible,
            value.deployment_authorized,
        )
        if rebuilt.to_canonical_dict() != value.to_canonical_dict():
            return None
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return rebuilt


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruPriceBarsSourceBoundedCaptureOutcomeV1:
    result: BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1 | None = None
    failure: BinanceUsdmKoruPriceBarsSourceBoundedFailureV1 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")
        if self.result is not None and _trusted_capture(self.result) is None:
            raise ValueError("capture outcome result is not canonical")
        if (
            self.failure is not None
            and type(self.failure) is not BinanceUsdmKoruPriceBarsSourceBoundedFailureV1
        ):
            raise TypeError("capture outcome failure must be exact")


def _fetch(
    url: str, fetch: FetchBytes
) -> tuple[
    bytes | None,
    int,
    BinanceUsdmKoruPriceBarsSourceBoundedFailureV1 | None,
]:
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = fetch(url)
        except (ConnectionError, OSError, RuntimeError, TimeoutError):
            response = None
        if response is None:
            if attempt == _MAX_ATTEMPTS:
                return (
                    None,
                    attempt,
                    _failure(
                        BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.PROVIDER_UNAVAILABLE,
                        url,
                    ),
                )
            continue
        if (
            type(response) is not tuple
            or len(response) != 2
            or type(response[0]) is not int
            or type(response[1]) is not bytes
        ):
            return (
                None,
                attempt,
                _failure(
                    BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.CONFIGURATION_INVALID,
                    url,
                ),
            )
        status, body = response
        if status == 200:
            return body, attempt, None
        if status in (401, 403):
            return (
                None,
                attempt,
                _failure(
                    BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.AUTHENTICATION_REJECTED,
                    url,
                ),
            )
        if status == 429:
            if attempt < _MAX_ATTEMPTS:
                continue
            return (
                None,
                attempt,
                _failure(
                    BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.RATE_LIMIT_EXHAUSTED,
                    url,
                ),
            )
        if 500 <= status <= 599:
            if attempt < _MAX_ATTEMPTS:
                continue
            return (
                None,
                attempt,
                _failure(
                    BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.PROVIDER_UNAVAILABLE,
                    url,
                ),
            )
        return (
            None,
            attempt,
            _failure(
                (
                    BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.DATA_GAP_DETECTED
                    if status == 404
                    else BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH
                ),
                url,
            ),
        )
    raise AssertionError("unreachable")


def capture_binance_usdm_koru_price_bars_source_bounded_v1(
    request: BinanceUsdmKoruPriceBarsSourceBoundedRequestV1,
    fetch: FetchBytes,
) -> BinanceUsdmKoruPriceBarsSourceBoundedCaptureOutcomeV1:
    trusted = _trusted_request(request)
    if trusted is None or trusted.authority is not None or not callable(fetch):
        return BinanceUsdmKoruPriceBarsSourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.CONFIGURATION_INVALID
            )
        )
    archive_url, checksum_url = trusted.urls
    archive, archive_attempts, archive_failure = _fetch(archive_url, fetch)
    checksum, checksum_attempts, checksum_failure = _fetch(checksum_url, fetch)
    if archive is not None and _sha256(archive) != trusted.expected_archive_sha256:
        archive_failure = _failure(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH,
            archive_url,
        )
    expected_checksum = (
        f"{trusted.expected_archive_sha256[7:]}  {trusted.archive_name}\n".encode()
    )
    if checksum is not None and (
        _sha256(checksum) != trusted.expected_checksum_sha256
        or checksum != expected_checksum
    ):
        checksum_failure = _failure(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH,
            checksum_url,
        )
    failures = tuple(
        failure
        for failure in (archive_failure, checksum_failure)
        if failure is not None
    )
    if failures:
        precedence = tuple(BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1)
        return BinanceUsdmKoruPriceBarsSourceBoundedCaptureOutcomeV1(
            failure=min(failures, key=lambda failure: precedence.index(failure.code))
        )
    if archive is None or checksum is None:
        return BinanceUsdmKoruPriceBarsSourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.CONFIGURATION_INVALID
            )
        )
    frozen = freeze_source_snapshot(
        members=(
            RawSourceMember(
                "archive/" + trusted.archive_name,
                archive,
                "0644",
                trusted.acquired_at_epoch_nanoseconds,
                trusted.expected_archive_sha256,
            ),
            RawSourceMember(
                "archive/" + trusted.checksum_name,
                checksum,
                "0644",
                trusted.acquired_at_epoch_nanoseconds,
                trusted.expected_checksum_sha256,
            ),
        ),
        provenance=_provenance(trusted),
    )
    if frozen.snapshot is None:
        return BinanceUsdmKoruPriceBarsSourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SNAPSHOT_INVALID
            )
        )
    try:
        result = BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1(
            trusted,
            frozen.snapshot,
            archive_attempts,
            checksum_attempts,
        )
    except (TypeError, ValueError):
        return BinanceUsdmKoruPriceBarsSourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SNAPSHOT_INVALID
            )
        )
    return BinanceUsdmKoruPriceBarsSourceBoundedCaptureOutcomeV1(result=result)


def capture_binance_usdm_koru_price_bars_from_retained_observations_v1(
    request: BinanceUsdmKoruPriceBarsSourceBoundedRequestV1,
    source_csv_bytes: bytes,
    base_manifest_bytes: bytes,
    derived_csv_bytes: bytes,
    archive_bytes: bytes,
    checksum_bytes: bytes,
) -> BinanceUsdmKoruPriceBarsSourceBoundedCaptureOutcomeV1:
    trusted = _trusted_request(request)
    if trusted is None or trusted.authority is None:
        return BinanceUsdmKoruPriceBarsSourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.CONFIGURATION_INVALID
            )
        )
    try:
        reconstructed = _reconstruct_retained_authority(
            trusted.source_kind,
            source_csv_bytes,
            base_manifest_bytes,
            derived_csv_bytes,
            archive_bytes,
            checksum_bytes,
        )
    except (BadZipFile, KeyError, OSError, RuntimeError, ValueError):
        reconstructed = None
    if (
        reconstructed is None
        or reconstructed.to_canonical_dict()
        != trusted.authority.to_canonical_dict()
        or _sha256(archive_bytes) != trusted.expected_archive_sha256
        or _sha256(checksum_bytes) != trusted.expected_checksum_sha256
    ):
        return BinanceUsdmKoruPriceBarsSourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH,
                "retained_authority",
            )
        )
    source_key = "retained/source/" + reconstructed.source_artifact_path.rsplit(
        "/", 1
    )[-1]
    frozen = freeze_source_snapshot(
        members=(
            RawSourceMember(
                source_key,
                source_csv_bytes,
                "0644",
                trusted.acquired_at_epoch_nanoseconds,
                reconstructed.source_artifact_sha256,
            ),
            RawSourceMember(
                _RETAINED_BASE_MANIFEST_MEMBER_KEY,
                base_manifest_bytes,
                "0644",
                trusted.acquired_at_epoch_nanoseconds,
                reconstructed.base_manifest_file_sha256,
            ),
            RawSourceMember(
                _RETAINED_DERIVED_CSV_MEMBER_KEY,
                derived_csv_bytes,
                "0644",
                trusted.acquired_at_epoch_nanoseconds,
                reconstructed.derived_csv_sha256,
            ),
            RawSourceMember(
                "derived/" + trusted.archive_name,
                archive_bytes,
                "0644",
                trusted.acquired_at_epoch_nanoseconds,
                trusted.expected_archive_sha256,
            ),
            RawSourceMember(
                "derived/" + trusted.checksum_name,
                checksum_bytes,
                "0644",
                trusted.acquired_at_epoch_nanoseconds,
                trusted.expected_checksum_sha256,
            ),
        ),
        provenance=_provenance(trusted),
    )
    if frozen.snapshot is None:
        return BinanceUsdmKoruPriceBarsSourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SNAPSHOT_INVALID
            )
        )
    try:
        result = BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1(
            trusted, frozen.snapshot, 1, 1
        )
    except (TypeError, ValueError):
        return BinanceUsdmKoruPriceBarsSourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SNAPSHOT_INVALID
            )
        )
    return BinanceUsdmKoruPriceBarsSourceBoundedCaptureOutcomeV1(result=result)


class _NormalizationError(ValueError):
    def __init__(
        self,
        code: BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1,
        subject: str,
        row_number: int | None = None,
    ) -> None:
        super().__init__(subject)
        self.code: BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1 = code
        self.subject: str = subject
        self.row_number: int | None = row_number


@dataclass(frozen=True, slots=True)
class _ParsedRow:
    open_time_milliseconds: int
    close_time_milliseconds: int
    open_units: int
    high_units: int
    low_units: int
    close_units: int
    exact_row: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _ReconstructedSource:
    requested_day_start: UtcInstant
    requested_day_end_exclusive: UtcInstant
    coverage_start: UtcInstant
    coverage_end_exclusive: UtcInstant
    authorized_projection_start: UtcInstant
    prefix_gap_classification: str
    retained_row_count: int
    projected_row_count: int
    excluded_prefix_row_count: int
    first_open_time_milliseconds: int
    last_open_time_milliseconds: int
    source_member_hash: str
    events: tuple[MarketEvent, ...]


def _canonical_integer(value: str) -> int:
    if _INTEGER.fullmatch(value) is None:
        raise ValueError("non-canonical integer")
    try:
        return int(value)
    except ValueError as error:
        raise ValueError("non-canonical integer") from error


def _canonical_nonnegative_decimal(value: str) -> None:
    if _DECIMAL.fullmatch(value) is None:
        raise ValueError("non-canonical decimal")


def _scale8_units(value: str) -> int:
    match = _PRICE.fullmatch(value)
    if match is None:
        raise ValueError("non-canonical scale8 decimal")
    fraction = match.group(1) or ""
    try:
        return int(value.partition(".")[0]) * 100_000_000 + int(
            fraction.ljust(8, "0") or "0"
        )
    except ValueError as error:
        raise ValueError("non-canonical scale8 decimal") from error


def _price_units(value: str) -> int:
    units = _scale8_units(value)
    if units <= 0:
        raise ValueError("price must be positive")
    return units


def _read_retained_csv(
    capture: BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1,
) -> bytes:
    request = capture.request
    prefix = _member_prefix(request)
    archive_key = prefix + request.archive_name
    checksum_key = prefix + request.checksum_name
    try:
        archive = capture.snapshot.member_bytes(archive_key)
        checksum = capture.snapshot.member_bytes(checksum_key)
    except ValueError as error:
        raise _NormalizationError(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "snapshot_member",
        ) from error
    if (
        _sha256(archive) != request.expected_archive_sha256
        or _sha256(checksum) != request.expected_checksum_sha256
        or checksum
        != f"{request.expected_archive_sha256[7:]}  {request.archive_name}\n".encode()
    ):
        raise _NormalizationError(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH,
            "checksum",
        )
    try:
        with ZipFile(io.BytesIO(archive)) as zip_file:
            if zip_file.namelist() != [request.csv_name]:
                raise _NormalizationError(
                    BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
                    "zip_member",
                )
            csv_bytes = zip_file.read(request.csv_name)
            if request.authority is not None:
                retained_csv = capture.snapshot.member_bytes(
                    _RETAINED_DERIVED_CSV_MEMBER_KEY
                )
                if (
                    csv_bytes != retained_csv
                    or _sha256(retained_csv) != request.authority.derived_csv_sha256
                ):
                    raise _NormalizationError(
                        BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH,
                        "derived_csv",
                    )
                return retained_csv
            return csv_bytes
    except _NormalizationError:
        raise
    except (
        BadZipFile,
        KeyError,
        NotImplementedError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        raise _NormalizationError(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "zip",
        ) from error


def _csv_rows(
    csv_bytes: bytes,
    header: tuple[str, ...] = _CSV_HEADER,
) -> list[list[str]]:
    if not csv_bytes or b"\r" in csv_bytes or not csv_bytes.endswith(b"\n"):
        raise _NormalizationError(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "csv_encoding",
        )
    try:
        text = csv_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise _NormalizationError(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "csv_encoding",
        ) from error
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error as error:
        raise _NormalizationError(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "csv",
        ) from error
    if not rows or tuple(rows[0]) != header:
        raise _NormalizationError(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "csv_header",
        )
    if len(rows) == 1:
        raise _NormalizationError(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
            "row_count",
        )
    canonical = "".join(",".join(row) + "\n" for row in rows).encode()
    if canonical != csv_bytes:
        raise _NormalizationError(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "csv_grammar",
        )
    return rows[1:]


def _iso_milliseconds(value: str) -> int:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
            tzinfo=UTC
        )
    except ValueError as error:
        raise ValueError("non-canonical UTC milliseconds") from error
    if parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z" != value:
        raise ValueError("non-canonical UTC milliseconds")
    delta = parsed - datetime(1970, 1, 1, tzinfo=UTC)
    return delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000


def _parse_retained_row(row: list[str], row_number: int) -> _ParsedRow:
    if len(row) != len(_RETAINED_CSV_HEADER):
        raise _NormalizationError(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "csv_columns",
            row_number,
        )
    try:
        open_time = _iso_milliseconds(row[0])
        open_units, high_units, low_units, close_units = tuple(
            _scale8_units(value) for value in row[1:5]
        )
        close_time = _iso_milliseconds(row[5])
        _ = _scale8_units(row[6])
    except (TypeError, ValueError) as error:
        raise _NormalizationError(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
            "row_value",
            row_number,
        ) from error
    if (
        not low_units <= open_units <= high_units
        or not low_units <= close_units <= high_units
    ):
        raise _NormalizationError(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
            "ohlc",
            row_number,
        )
    return _ParsedRow(
        open_time,
        close_time,
        open_units,
        high_units,
        low_units,
        close_units,
        tuple(row),
    )


def _parse_row(row: list[str], row_number: int) -> _ParsedRow:
    if len(row) != len(_CSV_HEADER):
        raise _NormalizationError(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "csv_columns",
            row_number,
        )
    try:
        open_time = _canonical_integer(row[0])
        open_units, high_units, low_units, close_units = tuple(
            _price_units(value) for value in row[1:5]
        )
        _canonical_nonnegative_decimal(row[5])
        close_time = _canonical_integer(row[6])
        _canonical_nonnegative_decimal(row[7])
        _ = _canonical_integer(row[8])
        for value in row[9:12]:
            _canonical_nonnegative_decimal(value)
    except (TypeError, ValueError) as error:
        raise _NormalizationError(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
            "row_value",
            row_number,
        ) from error
    if (
        not low_units <= open_units <= high_units
        or not low_units <= close_units <= high_units
    ):
        raise _NormalizationError(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
            "ohlc",
            row_number,
        )
    return _ParsedRow(
        open_time,
        close_time,
        open_units,
        high_units,
        low_units,
        close_units,
        tuple(row),
    )


def _validated_rows(
    rows: list[list[str]],
    requested_start: UtcInstant,
    requested_end: UtcInstant,
    *,
    retained: bool = False,
) -> tuple[_ParsedRow, ...]:
    day_start_ms = requested_start.epoch_nanoseconds // 1_000_000
    day_end_ms = requested_end.epoch_nanoseconds // 1_000_000
    parsed: list[_ParsedRow] = []
    observed: dict[int, tuple[str, ...]] = {}
    previous: _ParsedRow | None = None
    for row_number, row in enumerate(rows, 1):
        current = (
            _parse_retained_row(row, row_number)
            if retained
            else _parse_row(row, row_number)
        )
        duplicate = observed.get(current.open_time_milliseconds)
        if duplicate is not None:
            raise _NormalizationError(
                BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.DUPLICATE_OR_CONFLICT,
                "duplicate_hour"
                if duplicate == current.exact_row
                else "conflicting_hour",
                row_number,
            )
        observed[current.open_time_milliseconds] = current.exact_row
        if current.open_time_milliseconds % _HOUR_MILLISECONDS != 0:
            raise _NormalizationError(
                BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
                "hour_alignment",
                row_number,
            )
        if current.close_time_milliseconds != (
            current.open_time_milliseconds + _HOUR_MILLISECONDS - 1
        ):
            raise _NormalizationError(
                BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
                "closed_hour",
                row_number,
            )
        if not (
            day_start_ms <= current.open_time_milliseconds
            and current.close_time_milliseconds < day_end_ms
        ):
            raise _NormalizationError(
                BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
                "requested_date",
                row_number,
            )
        if previous is not None:
            if current.open_time_milliseconds < previous.open_time_milliseconds:
                raise _NormalizationError(
                    BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.ORDER_VIOLATION,
                    "hour_order",
                    row_number,
                )
            if current.open_time_milliseconds > (
                previous.open_time_milliseconds + _HOUR_MILLISECONDS
            ):
                raise _NormalizationError(
                    BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
                    "hour_gap",
                    row_number,
                )
        parsed.append(current)
        previous = current
    if retained and (
        not parsed
        or parsed[0].open_time_milliseconds != day_start_ms
        or parsed[-1].close_time_milliseconds + 1 != day_end_ms
    ):
        raise _NormalizationError(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
            "authority_coverage",
        )
    return tuple(parsed)


def _event_definitions(
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1,
) -> tuple[_EventDefinition, ...]:
    if source_kind is BinanceUsdmKoruPriceBarsSourceKindV1.MARK_PRICE:
        return _MARK_EVENT_DEFINITIONS
    return _INDEX_EVENT_DEFINITIONS


def _projection_policy(requested_start: UtcInstant) -> tuple[UtcInstant, str]:
    classification = (
        _AUTHORITY_PREFIX_CLASSIFICATION
        if requested_start < _AUTHORIZED_PROJECTION_START
        else _UNKNOWN_PREFIX_GAP_CLASSIFICATION
    )
    return _AUTHORIZED_PROJECTION_START, classification


def _event_from_row(
    capture: BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1,
    row: _ParsedRow,
    source_index: int,
    definition: _EventDefinition,
    source_member_hash: str,
) -> MarketEvent:
    request = capture.request
    archive_key = _member_prefix(request) + request.archive_name
    checksum_key = _member_prefix(request) + request.checksum_name
    archive_member = _snapshot_member(capture.snapshot, archive_key)
    checksum_member = _snapshot_member(capture.snapshot, checksum_key)
    snapshot_hash = canonical_sha256(capture.snapshot.to_canonical_dict())
    identity = {
        "type": "binance_usdm_koru_price_bar_event_identity_v1",
        "schema_version": _SCHEMA_VERSION,
        "snapshot_id": capture.snapshot.snapshot_id,
        "source_kind": request.source_kind.value,
        "open_time_milliseconds": row.open_time_milliseconds,
        "price_purpose": definition.price_purpose,
        "economic_availability_policy_ref": _ECONOMIC_AVAILABILITY_POLICY_REF,
    }
    if request.authority is not None:
        identity["retained_authority_hash"] = request.authority.authority_hash
        identity["provider_availability_authority_ref"] = (
            request.authority.provider_availability_authority_ref
        )
    payload = {
        "source_kind": request.source_kind.value,
        "price_purpose": definition.price_purpose,
        "interval": _INTERVAL,
        "open_time_milliseconds": row.open_time_milliseconds,
        "close_time_milliseconds": row.close_time_milliseconds,
        "open_units": row.open_units,
        "high_units": row.high_units,
        "low_units": row.low_units,
        "close_units": row.close_units,
        "price_scale": 8,
        "source_record_hash": canonical_sha256(row.exact_row),
        "request_hash": request.request_hash,
        "capture_hash": capture.capture_hash,
        "source_snapshot_id": capture.snapshot.snapshot_id,
        "source_snapshot_hash": snapshot_hash,
        "source_provenance_hash": capture.snapshot.provenance_hash,
        "source_member_key": request.csv_name,
        "source_member_hash": source_member_hash,
        "archive_member_key": archive_key,
        "archive_member_hash": archive_member.content_hash,
        "checksum_member_key": checksum_member.member_key,
        "checksum_member_hash": checksum_member.content_hash,
        "economic_availability_policy_ref": _ECONOMIC_AVAILABILITY_POLICY_REF,
        "archive_available_at_epoch_nanoseconds": request.archive_available_at_epoch_nanoseconds,
        "acquired_at_epoch_nanoseconds": request.acquired_at_epoch_nanoseconds,
    }
    if request.authority is not None:
        payload["source_mode"] = _RETAINED_SOURCE_MODE
        payload["retained_authority_hash"] = request.authority.authority_hash
        payload["provider_availability_authority_ref"] = (
            request.authority.provider_availability_authority_ref
        )
        payload["source_acquired_at_epoch_nanoseconds"] = (
            request.authority.source_acquired_at_epoch_nanoseconds
        )
        payload["local_retained_acquired_at_epoch_nanoseconds"] = (
            request.acquired_at_epoch_nanoseconds
        )
        payload["development_only"] = True
    if definition.point:
        payload["price_units"] = row.close_units
    retained_keys = (
        {
            "source_mode",
            "retained_authority_hash",
            "provider_availability_authority_ref",
            "source_acquired_at_epoch_nanoseconds",
            "local_retained_acquired_at_epoch_nanoseconds",
            "development_only",
        }
        if request.authority is not None
        else set()
    )
    expected_keys: frozenset[str] = _COMMON_PAYLOAD_KEYS | retained_keys | (
        {"price_units"} if definition.point else set()
    )
    if frozenset(payload) != expected_keys:
        raise AssertionError("event payload lineage is incomplete")
    completed = UtcInstant((row.close_time_milliseconds + 1) * 1_000_000)
    return MarketEvent(
        event_id="binance-usdm-koru-price-bar-v1:" + canonical_sha256(identity),
        stream_key=definition.stream_key,
        event_type=definition.event_type,
        capability=definition.capability,
        instrument_id=request.instrument_id,
        event_time=completed,
        available_time=completed,
        phase=_PHASE,
        source_sequence=SourceSequence(source_index),
        revision_id=archive_member.content_hash,
        supersedes_revision_id=None,
        source_key=capture.snapshot.provenance.source_key,
        source_hash=archive_member.content_hash,
        payload=payload,
    )


def _reconstruct_retained_source(
    capture: BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1,
) -> _ReconstructedSource:
    csv_bytes = _read_retained_csv(capture)
    requested_start, requested_end = _date_bounds(capture.request.utc_date)
    authority = capture.request.authority
    if authority is None:
        rows = _validated_rows(_csv_rows(csv_bytes), requested_start, requested_end)
    else:
        rows = _validated_rows(
            _csv_rows(csv_bytes, _RETAINED_CSV_HEADER),
            authority.selected_coverage_start,
            authority.selected_coverage_end_exclusive,
            retained=True,
        )
    authorized_projection_start, prefix_gap_classification = _projection_policy(
        requested_start
    )
    authorized_start_ms = authorized_projection_start.epoch_nanoseconds // 1_000_000
    projected_rows = tuple(
        row for row in rows if row.open_time_milliseconds >= authorized_start_ms
    )
    excluded_prefix_row_count = len(rows) - len(projected_rows)
    source_member_hash = _sha256(csv_bytes)
    try:
        events = tuple(
            _event_from_row(
                capture,
                row,
                source_index,
                definition,
                source_member_hash,
            )
            for source_index, row in enumerate(projected_rows)
            for definition in _event_definitions(capture.request.source_kind)
        )
    except (TypeError, ValueError) as error:
        raise _NormalizationError(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
            "market_event",
        ) from error
    return _ReconstructedSource(
        requested_day_start=requested_start,
        requested_day_end_exclusive=requested_end,
        coverage_start=UtcInstant(rows[0].open_time_milliseconds * 1_000_000),
        coverage_end_exclusive=UtcInstant(
            (rows[-1].close_time_milliseconds + 1) * 1_000_000
        ),
        authorized_projection_start=authorized_projection_start,
        prefix_gap_classification=prefix_gap_classification,
        retained_row_count=len(rows),
        projected_row_count=len(projected_rows),
        excluded_prefix_row_count=excluded_prefix_row_count,
        first_open_time_milliseconds=rows[0].open_time_milliseconds,
        last_open_time_milliseconds=rows[-1].open_time_milliseconds,
        source_member_hash=source_member_hash,
        events=events,
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1:
    capture: BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1
    source_kind: BinanceUsdmKoruPriceBarsSourceKindV1
    source_snapshot_id: str
    source_snapshot_hash: str
    request_hash: str
    capture_hash: str
    requested_day_start: UtcInstant
    requested_day_end_exclusive: UtcInstant
    coverage_start: UtcInstant
    coverage_end_exclusive: UtcInstant
    authorized_projection_start: UtcInstant
    economic_availability_policy_ref: str
    prefix_gap_classification: str
    suffix_gap_classification: str
    internal_gap_classification: str
    retained_row_count: int
    projected_row_count: int
    excluded_prefix_row_count: int
    first_open_time_milliseconds: int
    last_open_time_milliseconds: int
    source_member_hash: str
    events: tuple[MarketEvent, ...]
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        trusted = _trusted_capture(self.capture)
        if trusted is None:
            raise ValueError("normalization result capture is not canonical")
        try:
            reconstructed = _reconstruct_retained_source(trusted)
        except _NormalizationError as error:
            raise ValueError(
                "normalization result cannot reconstruct retained source"
            ) from error
        snapshot_hash = canonical_sha256(trusted.snapshot.to_canonical_dict())
        expected_events = reconstructed.events
        if (
            type(self.source_kind) is not BinanceUsdmKoruPriceBarsSourceKindV1
            or self.source_kind is not trusted.request.source_kind
            or self.source_snapshot_id != trusted.snapshot.snapshot_id
            or self.source_snapshot_hash != snapshot_hash
            or self.request_hash != trusted.request.request_hash
            or self.capture_hash != trusted.capture_hash
            or type(self.requested_day_start) is not UtcInstant
            or self.requested_day_start != reconstructed.requested_day_start
            or type(self.requested_day_end_exclusive) is not UtcInstant
            or self.requested_day_end_exclusive
            != reconstructed.requested_day_end_exclusive
            or type(self.coverage_start) is not UtcInstant
            or self.coverage_start != reconstructed.coverage_start
            or type(self.coverage_end_exclusive) is not UtcInstant
            or self.coverage_end_exclusive != reconstructed.coverage_end_exclusive
            or type(self.authorized_projection_start) is not UtcInstant
            or self.authorized_projection_start
            != reconstructed.authorized_projection_start
            or self.economic_availability_policy_ref
            != _ECONOMIC_AVAILABILITY_POLICY_REF
            or self.prefix_gap_classification != reconstructed.prefix_gap_classification
            or self.suffix_gap_classification != _SUFFIX_GAP_CLASSIFICATION
            or self.internal_gap_classification != _INTERNAL_GAP_CLASSIFICATION
            or type(self.events) is not tuple
            or any(type(event) is not MarketEvent for event in self.events)
            or self.events != expected_events
            or [event.to_canonical_dict() for event in self.events]
            != [event.to_canonical_dict() for event in expected_events]
            or type(self.retained_row_count) is not int
            or self.retained_row_count != reconstructed.retained_row_count
            or type(self.projected_row_count) is not int
            or self.projected_row_count != reconstructed.projected_row_count
            or type(self.excluded_prefix_row_count) is not int
            or self.excluded_prefix_row_count != reconstructed.excluded_prefix_row_count
            or type(self.first_open_time_milliseconds) is not int
            or self.first_open_time_milliseconds
            != reconstructed.first_open_time_milliseconds
            or type(self.last_open_time_milliseconds) is not int
            or self.last_open_time_milliseconds
            != reconstructed.last_open_time_milliseconds
            or self.source_member_hash != reconstructed.source_member_hash
        ):
            raise ValueError(
                "normalization result fields do not exactly reconstruct source"
            )
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("development-only qualification flags must remain false")

    @property
    def normalization_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_price_bars_source_bounded_normalization_result_v1",
            "schema_version": _SCHEMA_VERSION,
            "source_kind": self.source_kind.value,
            "source_snapshot_id": self.source_snapshot_id,
            "source_snapshot_hash": self.source_snapshot_hash,
            "request_hash": self.request_hash,
            "capture_hash": self.capture_hash,
            "requested_day_start": self.requested_day_start.to_canonical_dict(),
            "requested_day_end_exclusive": self.requested_day_end_exclusive.to_canonical_dict(),
            "coverage_start": self.coverage_start.to_canonical_dict(),
            "coverage_end_exclusive": self.coverage_end_exclusive.to_canonical_dict(),
            "authorized_projection_start": self.authorized_projection_start.to_canonical_dict(),
            "economic_availability_policy_ref": self.economic_availability_policy_ref,
            "prefix_gap_classification": self.prefix_gap_classification,
            "suffix_gap_classification": self.suffix_gap_classification,
            "internal_gap_classification": self.internal_gap_classification,
            "retained_row_count": self.retained_row_count,
            "projected_row_count": self.projected_row_count,
            "excluded_prefix_row_count": self.excluded_prefix_row_count,
            "first_open_time_milliseconds": self.first_open_time_milliseconds,
            "last_open_time_milliseconds": self.last_open_time_milliseconds,
            "source_member_hash": self.source_member_hash,
            "events": [event.to_canonical_dict() for event in self.events],
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


def _trusted_normalization_result(
    value: object,
) -> BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1 | None:
    if type(value) is not BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1:
        return None
    try:
        rebuilt = BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1(
            capture=value.capture,
            source_kind=value.source_kind,
            source_snapshot_id=value.source_snapshot_id,
            source_snapshot_hash=value.source_snapshot_hash,
            request_hash=value.request_hash,
            capture_hash=value.capture_hash,
            requested_day_start=value.requested_day_start,
            requested_day_end_exclusive=value.requested_day_end_exclusive,
            coverage_start=value.coverage_start,
            coverage_end_exclusive=value.coverage_end_exclusive,
            authorized_projection_start=value.authorized_projection_start,
            economic_availability_policy_ref=value.economic_availability_policy_ref,
            prefix_gap_classification=value.prefix_gap_classification,
            suffix_gap_classification=value.suffix_gap_classification,
            internal_gap_classification=value.internal_gap_classification,
            retained_row_count=value.retained_row_count,
            projected_row_count=value.projected_row_count,
            excluded_prefix_row_count=value.excluded_prefix_row_count,
            first_open_time_milliseconds=value.first_open_time_milliseconds,
            last_open_time_milliseconds=value.last_open_time_milliseconds,
            source_member_hash=value.source_member_hash,
            events=value.events,
            decision_grade_eligible=value.decision_grade_eligible,
            deployment_authorized=value.deployment_authorized,
        )
        if rebuilt.to_canonical_dict() != value.to_canonical_dict():
            return None
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return rebuilt


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruPriceBarsSourceBoundedNormalizationOutcomeV1:
    result: BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1 | None = None
    failure: BinanceUsdmKoruPriceBarsSourceBoundedFailureV1 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")
        if (
            self.result is not None
            and _trusted_normalization_result(self.result) is None
        ):
            raise ValueError("normalization outcome result is not canonical")
        if (
            self.failure is not None
            and type(self.failure) is not BinanceUsdmKoruPriceBarsSourceBoundedFailureV1
        ):
            raise TypeError("normalization outcome failure must be exact")


def _normalization_failure(
    code: BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1,
    subject: str,
    row_number: int | None = None,
) -> BinanceUsdmKoruPriceBarsSourceBoundedNormalizationOutcomeV1:
    return BinanceUsdmKoruPriceBarsSourceBoundedNormalizationOutcomeV1(
        failure=_failure(code, subject, row_number)
    )


def normalize_binance_usdm_koru_price_bars_source_bounded_v1(
    capture: BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1,
) -> BinanceUsdmKoruPriceBarsSourceBoundedNormalizationOutcomeV1:
    trusted = _trusted_capture(capture)
    if trusted is None:
        return _normalization_failure(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.CONFIGURATION_INVALID,
            "capture",
        )
    try:
        reconstructed = _reconstruct_retained_source(trusted)
        result = BinanceUsdmKoruPriceBarsSourceBoundedNormalizationResultV1(
            capture=trusted,
            source_kind=trusted.request.source_kind,
            source_snapshot_id=trusted.snapshot.snapshot_id,
            source_snapshot_hash=canonical_sha256(trusted.snapshot.to_canonical_dict()),
            request_hash=trusted.request.request_hash,
            capture_hash=trusted.capture_hash,
            requested_day_start=reconstructed.requested_day_start,
            requested_day_end_exclusive=reconstructed.requested_day_end_exclusive,
            coverage_start=reconstructed.coverage_start,
            coverage_end_exclusive=reconstructed.coverage_end_exclusive,
            authorized_projection_start=reconstructed.authorized_projection_start,
            economic_availability_policy_ref=_ECONOMIC_AVAILABILITY_POLICY_REF,
            prefix_gap_classification=reconstructed.prefix_gap_classification,
            suffix_gap_classification=_SUFFIX_GAP_CLASSIFICATION,
            internal_gap_classification=_INTERNAL_GAP_CLASSIFICATION,
            retained_row_count=reconstructed.retained_row_count,
            projected_row_count=reconstructed.projected_row_count,
            excluded_prefix_row_count=reconstructed.excluded_prefix_row_count,
            first_open_time_milliseconds=reconstructed.first_open_time_milliseconds,
            last_open_time_milliseconds=reconstructed.last_open_time_milliseconds,
            source_member_hash=reconstructed.source_member_hash,
            events=reconstructed.events,
        )
    except _NormalizationError as error:
        return _normalization_failure(error.code, error.subject, error.row_number)
    except (KeyError, TypeError, ValueError):
        return _normalization_failure(
            BinanceUsdmKoruPriceBarsSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
            "normalization_result",
        )
    return BinanceUsdmKoruPriceBarsSourceBoundedNormalizationOutcomeV1(result=result)
