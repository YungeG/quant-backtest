"""KORU aggregate-trade source capture with sealed retained-data authority."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import tarfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import Enum
from itertools import pairwise
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from crypto_quant_domain import (
    InstrumentId,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
    VenueId,
    canonical_bytes,
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
_INSTRUMENT = InstrumentId(
    VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual"
)
_POST_ADJUSTMENT_START = date(2026, 7, 15)
_EPOCH_DATE = date(1970, 1, 1)
_DAY_NANOSECONDS = 86_400_000_000_000
_BASE_URL = "https://data.binance.vision/data/futures/um/daily/aggTrades/KORUUSDT/"
_RETAINED_ENDPOINT = "https://fapi.binance.com/fapi/v1/aggTrades"
_RETAINED_SOURCE_MODE = "execution_manifest_bounded_rest_observations"
_RETAINED_UTC_DATE = "2026-08-24"
_RETAINED_DAY_START_MS = 1_787_529_600_000
_RETAINED_COVERAGE_START_MS = 1_787_553_260_640
_RETAINED_COVERAGE_END_MS = 1_787_569_200_000
_RETAINED_AVAILABILITY_POLICY_KEY = "binance.fapi.aggtrade.transaction-time"
_RETAINED_AVAILABILITY_POLICY_VERSION = 1
_RETAINED_AVAILABILITY_APPROVED_COMMIT = (
    "27401e5cbee82a9ba50533285831f5a2458cab6a"
)
_RETAINED_AVAILABILITY_CONTRACT_FILE_SHA256 = (
    "sha256:7b88488086f668406c5e669f4943ec65e85677c08eec3b3f48201fb1de5ec2e4"
)
_RETAINED_EXECUTION_MANIFEST_PATH = "research/koruusdt/data/execution_data_manifest.json"
_RETAINED_AVAILABILITY_AUTHORITY_MEMBER_KEY = (
    "retained/availability/authority.json"
)
_RETAINED_EXECUTION_MANIFEST_MEMBER_KEY = "retained/execution/manifest.json"
_RETAINED_RAW_PATH_PREFIX = (
    "binance_usdm/aggTrades/rest-bounded/2026-08-24/"
)
_RETAINED_DERIVED_CSV_NAME = (
    "KORUUSDT-aggTrades-2026-08-24.discovery-bounded.csv"
)
_RETAINED_DERIVED_CSV_MEMBER_KEY = "derived/" + _RETAINED_DERIVED_CSV_NAME
_CSV_HEADER = (
    "agg_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "transact_time",
    "is_buyer_maker",
)
_RETAINED_CSV_SCHEMA_IDENTITY = "binance_usdm_aggtrades_csv_7_column_v1"
_MAX_ATTEMPTS = 3
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_INTEGER = re.compile(r"(?:0|[1-9][0-9]*)\Z")
_DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)\.[0-9]+\Z")
_PHASE = TimelinePhase(0, "market_data")
_CAPABILITY = MarketBundleCapability(
    "price.aggregate_trade.koru-usdt-tradifi-perpetual", 1
)
_STREAM_KEY = "binance_usdm.aggregate_trades.execution_reference.koruusdt.tradifi.v1"
_EVENT_TYPE = "binance_usdm_koru_aggregate_trade.v1"
_PREFIX_GAP_CLASSIFICATION = "unknown_unproven"
_SUFFIX_GAP_CLASSIFICATION = "unknown_unproven"
_INTERNAL_GAP_CLASSIFICATION = "none_observed_by_contiguous_ids"
_RAW_ID_GAP_CLASSIFICATION = (
    "provider_raw_id_gaps_observed_with_contiguous_aggregate_ids"
)
_EVENT_PAYLOAD_KEYS = frozenset(
    {
        "price_purpose",
        "aggregate_trade_id",
        "first_trade_id",
        "last_trade_id",
        "price",
        "quantity",
        "is_buyer_maker",
        "transaction_time_milliseconds",
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
        "archive_available_at_epoch_nanoseconds",
        "acquired_at_epoch_nanoseconds",
    }
)

FetchBytes = Callable[[str], tuple[int, bytes]]


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _archive_name(utc_date: str) -> str:
    return f"{_SYMBOL}-aggTrades-{utc_date}.zip"


def _checksum_name(utc_date: str) -> str:
    return _archive_name(utc_date) + ".CHECKSUM"


def _csv_name(utc_date: str) -> str:
    return f"{_SYMBOL}-aggTrades-{utc_date}.csv"


def _source_key(utc_date: str, archive_available_at_epoch_nanoseconds: int) -> str:
    return (
        "binance.public_data.futures.um.daily.aggtrades.koruusdt."
        f"{utc_date}.archive-available-at-{archive_available_at_epoch_nanoseconds}"
    )


def _date_value(value: object) -> date:
    if type(value) is not str:
        raise ValueError("utc_date must be an exact ISO UTC date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise ValueError("utc_date must be an exact ISO UTC date") from error
    if parsed.isoformat() != value or parsed < _POST_ADJUSTMENT_START:
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


def _iso_milliseconds(value: object) -> int:
    if type(value) is not str:
        raise ValueError("time must be exact UTC milliseconds")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC)
    except ValueError as error:
        raise ValueError("time must be exact UTC milliseconds") from error
    if parsed.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4] + "Z" != value:
        raise ValueError("time must be exact UTC milliseconds")
    delta = parsed - datetime(1970, 1, 1, tzinfo=UTC)
    return delta.days * 86_400_000 + delta.seconds * 1000 + delta.microseconds // 1000


def _page_time_token(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, tz=UTC).strftime("%Y%m%dT%H%M%SZ")


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruAggregateTradeAvailabilityAuthorityV1:
    """Approved KORU simulation/source contract identity, never acquisition inference."""

    policy_key: str
    policy_version: int
    approved_commit: str
    contract_file_sha256: str
    source_event_field: str
    semantics: str
    instrument_scope: str
    simulation_scope: str
    development_only: bool = True
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if (
            self.policy_key != _RETAINED_AVAILABILITY_POLICY_KEY
            or type(self.policy_version) is not int
            or self.policy_version != _RETAINED_AVAILABILITY_POLICY_VERSION
            or self.approved_commit != _RETAINED_AVAILABILITY_APPROVED_COMMIT
            or self.contract_file_sha256
            != _RETAINED_AVAILABILITY_CONTRACT_FILE_SHA256
            or self.source_event_field != "T"
            or self.semantics != "available_time_equals_retained_trade_time"
            or self.instrument_scope != "KORU"
            or self.simulation_scope != "first_retained_trade"
        ):
            raise ValueError("KORU aggTrade availability authority must be exact")
        _content_hash("contract_file_sha256", self.contract_file_sha256)
        if (
            type(self.development_only) is not bool
            or not self.development_only
            or type(self.decision_grade_eligible) is not bool
            or self.decision_grade_eligible
            or type(self.deployment_authorized) is not bool
            or self.deployment_authorized
        ):
            raise ValueError("KORU aggTrade availability authority is development-only")

    @property
    def authority_ref(self) -> str:
        return f"{self.policy_key}.v{self.policy_version}"

    @property
    def authority_digest(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_aggregate_trade_availability_authority_v1",
            "schema_version": _SCHEMA_VERSION,
            "policy_key": self.policy_key,
            "policy_version": self.policy_version,
            "approved_commit": self.approved_commit,
            "contract_file_sha256": self.contract_file_sha256,
            "source_event_field": self.source_event_field,
            "semantics": self.semantics,
            "instrument_scope": self.instrument_scope,
            "simulation_scope": self.simulation_scope,
            "development_only": self.development_only,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1 = (
    BinanceUsdmKoruAggregateTradeAvailabilityAuthorityV1(
        policy_key=_RETAINED_AVAILABILITY_POLICY_KEY,
        policy_version=_RETAINED_AVAILABILITY_POLICY_VERSION,
        approved_commit=_RETAINED_AVAILABILITY_APPROVED_COMMIT,
        contract_file_sha256=_RETAINED_AVAILABILITY_CONTRACT_FILE_SHA256,
        source_event_field="T",
        semantics="available_time_equals_retained_trade_time",
        instrument_scope="KORU",
        simulation_scope="first_retained_trade",
    )
)


def _trusted_availability_authority(
    value: object,
) -> BinanceUsdmKoruAggregateTradeAvailabilityAuthorityV1 | None:
    if type(value) is not BinanceUsdmKoruAggregateTradeAvailabilityAuthorityV1:
        return None
    try:
        rebuilt = BinanceUsdmKoruAggregateTradeAvailabilityAuthorityV1(
            policy_key=_RETAINED_AVAILABILITY_POLICY_KEY,
            policy_version=_RETAINED_AVAILABILITY_POLICY_VERSION,
            approved_commit=_RETAINED_AVAILABILITY_APPROVED_COMMIT,
            contract_file_sha256=_RETAINED_AVAILABILITY_CONTRACT_FILE_SHA256,
            source_event_field="T",
            semantics="available_time_equals_retained_trade_time",
            instrument_scope="KORU",
            simulation_scope="first_retained_trade",
            development_only=True,
            decision_grade_eligible=False,
            deployment_authorized=False,
        )
        if canonical_bytes(rebuilt.to_canonical_dict()) != canonical_bytes(
            value.to_canonical_dict()
        ):
            return None
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt


def _availability_authority_bytes() -> bytes:
    trusted = _trusted_availability_authority(
        BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1
    )
    if trusted is None:
        raise ValueError("KORU aggTrade availability authority must be exact")
    return canonical_bytes(trusted.to_canonical_dict())


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruRetainedAggregateTradesPageV1:
    member_name: str
    content_sha256: str
    source_url: str
    request_start_time_milliseconds: int
    request_end_time_milliseconds: int
    page_number: int
    row_count: int
    from_aggregate_trade_id: int | None = None

    def __post_init__(self) -> None:
        _content_hash("content_sha256", self.content_sha256)
        values = (
            self.request_start_time_milliseconds,
            self.request_end_time_milliseconds,
            self.page_number,
            self.row_count,
        )
        if any(type(value) is not int or value <= 0 for value in values):
            raise ValueError("retained page bounds and counts must be positive integers")
        if (
            self.request_start_time_milliseconds < _RETAINED_COVERAGE_START_MS
            or self.request_end_time_milliseconds
            >= _RETAINED_COVERAGE_END_MS
            or self.request_start_time_milliseconds
            > self.request_end_time_milliseconds
            or self.row_count > 1000
            or (
                self.from_aggregate_trade_id is not None
                and (
                    type(self.from_aggregate_trade_id) is not int
                    or self.from_aggregate_trade_id < 0
                )
            )
        ):
            raise ValueError("retained page must stay inside the exact holdout window")
        expected_name = (
            f"{_SYMBOL}-aggTrades-"
            f"{_page_time_token(self.request_start_time_milliseconds)}-"
            f"{_page_time_token(self.request_end_time_milliseconds)}-"
            f"page-{self.page_number:04d}.json"
        )
        if self.member_name != expected_name:
            raise ValueError("retained page member name must be canonical")
        expected_url = (
            f"{_RETAINED_ENDPOINT}?symbol={_SYMBOL}"
            f"&startTime={self.request_start_time_milliseconds}"
            f"&endTime={self.request_end_time_milliseconds}&limit=1000"
        )
        if self.from_aggregate_trade_id is not None:
            expected_url += f"&fromId={self.from_aggregate_trade_id}"
        if self.source_url != expected_url:
            raise ValueError("retained page source URL must be exact")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "member_name": self.member_name,
            "content_sha256": self.content_sha256,
            "source_url": self.source_url,
            "request_start_time_milliseconds": self.request_start_time_milliseconds,
            "request_end_time_milliseconds": self.request_end_time_milliseconds,
            "page_number": self.page_number,
            "row_count": self.row_count,
            "from_aggregate_trade_id": self.from_aggregate_trade_id,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruRetainedAggregateTradesAuthorityV1:
    execution_manifest_path: str
    execution_manifest_file_sha256: str
    execution_manifest_identity: str
    execution_manifest_generated_at_epoch_nanoseconds: int
    pages: tuple[BinanceUsdmKoruRetainedAggregateTradesPageV1, ...]
    selected_coverage_start: UtcInstant
    selected_coverage_end_exclusive: UtcInstant
    declared_missing_prefix_start: UtcInstant
    declared_missing_prefix_end_exclusive: UtcInstant
    availability_authority: BinanceUsdmKoruAggregateTradeAvailabilityAuthorityV1
    derived_csv_member_name: str
    derived_csv_sha256: str
    derived_csv_schema_identity: str
    provider_archive_claim: bool = False
    development_only: bool = True
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if self.execution_manifest_path != _RETAINED_EXECUTION_MANIFEST_PATH:
            raise ValueError("execution manifest path must be exact")
        _content_hash(
            "execution_manifest_file_sha256", self.execution_manifest_file_sha256
        )
        _content_hash("execution_manifest_identity", self.execution_manifest_identity)
        if (
            type(self.execution_manifest_generated_at_epoch_nanoseconds) is not int
            or self.execution_manifest_generated_at_epoch_nanoseconds <= 0
            or type(self.pages) is not tuple
            or not self.pages
            or any(
                type(page) is not BinanceUsdmKoruRetainedAggregateTradesPageV1
                for page in self.pages
            )
        ):
            raise ValueError("retained authority must bind exact local page evidence")
        expected_order = tuple(
            sorted(
                self.pages,
                key=lambda page: (
                    page.request_start_time_milliseconds,
                    page.page_number,
                ),
            )
        )
        if self.pages != expected_order or len(
            {page.member_name for page in self.pages}
        ) != len(self.pages):
            raise ValueError("retained pages must use canonical unique order")
        previous: BinanceUsdmKoruRetainedAggregateTradesPageV1 | None = None
        for page in self.pages:
            if previous is None or (
                page.request_start_time_milliseconds
                != previous.request_start_time_milliseconds
            ):
                if page.page_number != 1 or page.from_aggregate_trade_id is not None:
                    raise ValueError("each retained request window must start at page one")
                if previous is not None and (
                    page.request_start_time_milliseconds
                    != previous.request_end_time_milliseconds + 1
                ):
                    raise ValueError("retained request windows must be contiguous")
            elif (
                page.page_number != previous.page_number + 1
                or page.from_aggregate_trade_id is None
                or previous.row_count != 1000
            ):
                raise ValueError("retained page numbers and fromId must be contiguous")
            previous = page
        if (
            self.pages[0].request_start_time_milliseconds
            != _RETAINED_COVERAGE_START_MS
            or self.pages[-1].request_end_time_milliseconds
            != _RETAINED_COVERAGE_END_MS - 1
        ):
            raise ValueError("retained pages must exactly cover the selected window")
        expected_instants = (
            (self.selected_coverage_start, _RETAINED_COVERAGE_START_MS),
            (self.selected_coverage_end_exclusive, _RETAINED_COVERAGE_END_MS),
            (self.declared_missing_prefix_start, _RETAINED_DAY_START_MS),
            (
                self.declared_missing_prefix_end_exclusive,
                _RETAINED_COVERAGE_START_MS,
            ),
        )
        if any(
            type(instant) is not UtcInstant
            or instant.epoch_nanoseconds != milliseconds * 1_000_000
            for instant, milliseconds in expected_instants
        ):
            raise ValueError("retained coverage and missing prefix must be exact")
        availability_authority = _trusted_availability_authority(
            self.availability_authority
        )
        if (
            availability_authority is None
            or self.derived_csv_member_name != _RETAINED_DERIVED_CSV_NAME
            or self.derived_csv_schema_identity != _RETAINED_CSV_SCHEMA_IDENTITY
        ):
            raise ValueError("retained schema and availability authority must be exact")
        object.__setattr__(
            self, "availability_authority", availability_authority
        )
        _content_hash("derived_csv_sha256", self.derived_csv_sha256)
        if (
            type(self.provider_archive_claim) is not bool
            or self.provider_archive_claim
            or type(self.development_only) is not bool
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
        availability_authority = _trusted_availability_authority(
            self.availability_authority
        )
        if availability_authority is None:
            raise ValueError("retained availability authority must be exact")
        return {
            "type": "binance_usdm_koru_retained_aggregate_trades_authority_v1",
            "schema_version": _SCHEMA_VERSION,
            "execution_manifest_path": self.execution_manifest_path,
            "execution_manifest_file_sha256": self.execution_manifest_file_sha256,
            "execution_manifest_identity": self.execution_manifest_identity,
            "execution_manifest_generated_at_epoch_nanoseconds": self.execution_manifest_generated_at_epoch_nanoseconds,
            "pages": [page.to_canonical_dict() for page in self.pages],
            "selected_coverage_start": self.selected_coverage_start.to_canonical_dict(),
            "selected_coverage_end_exclusive": self.selected_coverage_end_exclusive.to_canonical_dict(),
            "declared_missing_prefix_start": self.declared_missing_prefix_start.to_canonical_dict(),
            "declared_missing_prefix_end_exclusive": self.declared_missing_prefix_end_exclusive.to_canonical_dict(),
            "availability_authority": availability_authority.to_canonical_dict(),
            "availability_authority_ref": availability_authority.authority_ref,
            "availability_authority_digest": availability_authority.authority_digest,
            "derived_csv_member_name": self.derived_csv_member_name,
            "derived_csv_sha256": self.derived_csv_sha256,
            "derived_csv_schema_identity": self.derived_csv_schema_identity,
            "provider_archive_claim": self.provider_archive_claim,
            "development_only": self.development_only,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


def _trusted_authority(
    value: object,
) -> BinanceUsdmKoruRetainedAggregateTradesAuthorityV1 | None:
    if type(value) is not BinanceUsdmKoruRetainedAggregateTradesAuthorityV1:
        return None
    try:
        availability_authority = _trusted_availability_authority(
            value.availability_authority
        )
        if availability_authority is None:
            return None
        rebuilt = BinanceUsdmKoruRetainedAggregateTradesAuthorityV1(
            execution_manifest_path=value.execution_manifest_path,
            execution_manifest_file_sha256=value.execution_manifest_file_sha256,
            execution_manifest_identity=value.execution_manifest_identity,
            execution_manifest_generated_at_epoch_nanoseconds=value.execution_manifest_generated_at_epoch_nanoseconds,
            pages=value.pages,
            selected_coverage_start=value.selected_coverage_start,
            selected_coverage_end_exclusive=value.selected_coverage_end_exclusive,
            declared_missing_prefix_start=value.declared_missing_prefix_start,
            declared_missing_prefix_end_exclusive=value.declared_missing_prefix_end_exclusive,
            availability_authority=availability_authority,
            derived_csv_member_name=value.derived_csv_member_name,
            derived_csv_sha256=value.derived_csv_sha256,
            derived_csv_schema_identity=value.derived_csv_schema_identity,
            provider_archive_claim=value.provider_archive_claim,
            development_only=value.development_only,
            decision_grade_eligible=value.decision_grade_eligible,
            deployment_authorized=value.deployment_authorized,
        )
        if rebuilt.to_canonical_dict() != value.to_canonical_dict():
            return None
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt


def _provenance(
    request: BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1,
) -> SourceSnapshotProvenance:
    if request.authority is not None:
        authority = _trusted_authority(request.authority)
        if authority is None:
            raise ValueError("retained availability authority must be exact")
        availability_authority = authority.availability_authority
        return SourceSnapshotProvenance(
            vendor_key="repository.retained_binance_observations",
            source_key=(
                "binance.fapi.bounded-rest.koruusdt.aggtrades.2026-08-24."
                + availability_authority.authority_ref
                + ".availability-"
                + availability_authority.authority_digest[7:]
                + ".retained-"
                + authority.authority_hash[7:]
            ),
            license_ref="binance.api.terms",
            retention_policy_ref="development.retained-observation-authority.v1",
        )
    return SourceSnapshotProvenance(
        vendor_key="binance.public_data",
        source_key=_source_key(
            request.utc_date, request.archive_available_at_epoch_nanoseconds
        ),
        license_ref="binance.public_data.terms",
        retention_policy_ref="backtest.fixture.retention",
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1:
    instrument_id: InstrumentId
    utc_date: str
    archive_available_at_epoch_nanoseconds: int
    acquired_at_epoch_nanoseconds: int
    expected_archive_sha256: str
    expected_checksum_sha256: str
    authority: BinanceUsdmKoruRetainedAggregateTradesAuthorityV1 | None = None

    def __post_init__(self) -> None:
        if type(self.instrument_id) is not InstrumentId or self.instrument_id != _INSTRUMENT:
            raise ValueError("instrument_id must be the exact KORU tradifi perpetual")
        _, day_end = _date_bounds(self.utc_date)
        if type(self.archive_available_at_epoch_nanoseconds) is not int:
            raise ValueError("archive_available_at must be an exact UTC instant")
        if type(self.acquired_at_epoch_nanoseconds) is not int:
            raise ValueError("acquired_at must be an exact UTC instant")
        archive_available_at = UtcInstant(
            self.archive_available_at_epoch_nanoseconds
        )
        acquired_at = UtcInstant(self.acquired_at_epoch_nanoseconds)
        if archive_available_at < day_end:
            raise ValueError("archive_available_at cannot precede requested UTC day end")
        if acquired_at < archive_available_at:
            raise ValueError("acquired_at cannot precede archive_available_at")
        _content_hash("expected_archive_sha256", self.expected_archive_sha256)
        _content_hash("expected_checksum_sha256", self.expected_checksum_sha256)
        if self.authority is not None:
            authority = _trusted_authority(self.authority)
            if (
                authority is None
                or self.utc_date != _RETAINED_UTC_DATE
                or self.archive_available_at_epoch_nanoseconds
                < authority.execution_manifest_generated_at_epoch_nanoseconds
                or self.acquired_at_epoch_nanoseconds
                < authority.execution_manifest_generated_at_epoch_nanoseconds
            ):
                raise ValueError("retained request authority does not exactly bind Aug24")
            object.__setattr__(self, "authority", authority)

    @property
    def archive_name(self) -> str:
        if self.authority is not None:
            return self.authority.derived_csv_member_name.removesuffix(".csv") + ".zip"
        return _archive_name(self.utc_date)

    @property
    def checksum_name(self) -> str:
        if self.authority is not None:
            return self.archive_name + ".CHECKSUM"
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
        return (
            _BASE_URL + self.archive_name,
            _BASE_URL + self.checksum_name,
        )

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        if self.authority is None:
            archive_url, checksum_url = self.urls
            return {
                "type": "binance_usdm_koru_aggregate_trades_source_bounded_request_v1",
                "schema_version": _SCHEMA_VERSION,
                "instrument_id": self.instrument_id.to_canonical_dict(),
                "symbol": _SYMBOL,
                "utc_date": self.utc_date,
                "archive_url": archive_url,
                "checksum_url": checksum_url,
                "archive_available_at_epoch_nanoseconds": self.archive_available_at_epoch_nanoseconds,
                "acquired_at_epoch_nanoseconds": self.acquired_at_epoch_nanoseconds,
                "expected_archive_sha256": self.expected_archive_sha256,
                "expected_checksum_sha256": self.expected_checksum_sha256,
            }
        authority = _trusted_authority(self.authority)
        if authority is None:
            raise ValueError("retained request authority must be exact")
        availability_authority = authority.availability_authority
        return {
            "type": "binance_usdm_koru_aggregate_trades_source_bounded_request_v1",
            "schema_version": _SCHEMA_VERSION,
            "instrument_id": self.instrument_id.to_canonical_dict(),
            "symbol": _SYMBOL,
            "utc_date": self.utc_date,
            "source_mode": _RETAINED_SOURCE_MODE,
            "provider_archive_claim": False,
            "authority": authority.to_canonical_dict(),
            "authority_hash": authority.authority_hash,
            "availability_authority_ref": availability_authority.authority_ref,
            "availability_authority_digest": availability_authority.authority_digest,
            "archive_available_at_epoch_nanoseconds": self.archive_available_at_epoch_nanoseconds,
            "acquired_at_epoch_nanoseconds": self.acquired_at_epoch_nanoseconds,
            "expected_archive_sha256": self.expected_archive_sha256,
            "expected_checksum_sha256": self.expected_checksum_sha256,
        }


def _trusted_request(
    value: object,
) -> BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1 | None:
    if type(value) is not BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1:
        return None
    try:
        rebuilt = BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1(
            value.instrument_id,
            value.utc_date,
            value.archive_available_at_epoch_nanoseconds,
            value.acquired_at_epoch_nanoseconds,
            value.expected_archive_sha256,
            value.expected_checksum_sha256,
            value.authority,
        )
        if rebuilt.to_canonical_dict() != value.to_canonical_dict():
            return None
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt


class BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1(str, Enum):
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
class BinanceUsdmKoruAggregateTradesSourceBoundedFailureV1:
    code: BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1
    subject: str | None = None
    row_number: int | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1:
            raise TypeError("code must be an exact KORU source-bounded failure code")
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
            "type": "binance_usdm_koru_aggregate_trades_source_bounded_failure_v1",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
            "row_number": self.row_number,
        }


def _failure(
    code: BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1,
    subject: str | None = None,
    row_number: int | None = None,
) -> BinanceUsdmKoruAggregateTradesSourceBoundedFailureV1:
    return BinanceUsdmKoruAggregateTradesSourceBoundedFailureV1(
        code, subject, row_number
    )


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


def _execution_manifest(execution_manifest_bytes: bytes) -> dict[str, object]:
    if type(execution_manifest_bytes) is not bytes:
        raise ValueError("execution manifest must be exact bytes")
    try:
        value = json.loads(
            execution_manifest_bytes, object_pairs_hook=_json_object
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("execution manifest must be exact JSON") from error
    if type(value) is not dict:
        raise ValueError("execution manifest must be a JSON object")
    declared = value.get("manifest_sha256")
    if type(declared) is not str or declared != _manifest_sha256(value):
        raise ValueError("execution manifest canonical hash mismatch")
    schema_version = value.get("schema_version")
    if value.get("type") != "koruusdt_execution_data_manifest" or schema_version not in (
        2,
        3,
    ):
        raise ValueError("execution manifest identity mismatch")
    if schema_version == 3:
        metadata = value.get("official_archive_metadata_receipt")
        if (
            not isinstance(metadata, dict)
            or set(metadata)
            != {"path", "file_sha256", "receipt_sha256", "file_count"}
            or metadata.get("path")
            != "binance_usdm/official_archive_metadata_receipt.json"
            or type(metadata.get("file_count")) is not int
            or metadata.get("file_count") != 240
        ):
            raise ValueError("execution manifest metadata receipt mismatch")
        _content_hash("metadata_receipt_file_sha256", metadata.get("file_sha256"))
        _content_hash("metadata_receipt_sha256", metadata.get("receipt_sha256"))
    return value


def _exact_mapping(value: object, expected: dict[str, object]) -> bool:
    return type(value) is dict and value == expected


def _manifest_files(manifest: dict[str, object]) -> list[dict[str, object]]:
    files = manifest.get("files")
    if type(files) is not list or any(type(value) is not dict for value in files):
        raise ValueError("execution manifest files missing")
    paths = [value.get("path") for value in files]
    if any(type(path) is not str for path in paths) or len(paths) != len(set(paths)):
        raise ValueError("execution manifest file paths must be unique")
    return files  # type: ignore[return-value]


def _manifest_file(
    files: list[dict[str, object]], path: str, status: str
) -> dict[str, object]:
    matches = [value for value in files if value.get("path") == path]
    if (
        len(matches) != 1
        or matches[0].get("status") != status
        or matches[0].get("source_url") != _RETAINED_ENDPOINT
        or matches[0].get("provider_checksum") is not None
    ):
        raise ValueError("execution manifest file entry mismatch")
    _content_hash("manifest file sha256", matches[0].get("sha256"))
    size_bytes = matches[0].get("size_bytes")
    row_count = matches[0].get("row_count")
    if (
        type(size_bytes) is not int
        or size_bytes < 0
        or type(row_count) is not int
        or row_count <= 0
    ):
        raise ValueError("execution manifest file metadata mismatch")
    return matches[0]


def _page_from_manifest_entry(
    entry: dict[str, object], expected_page_number: int | None
) -> BinanceUsdmKoruRetainedAggregateTradesPageV1:
    path = entry.get("path")
    source_url = entry.get("source_url")
    if (
        type(path) is not str
        or not path.startswith(_RETAINED_RAW_PATH_PREFIX)
        or type(source_url) is not str
        or entry.get("status") != "canonical_rest_response"
        or entry.get("provider_checksum") is not None
    ):
        raise ValueError("retained page manifest entry mismatch")
    member_name = path.removeprefix(_RETAINED_RAW_PATH_PREFIX)
    match = re.fullmatch(
        rf"{_SYMBOL}-aggTrades-[0-9]{{8}}T[0-9]{{6}}Z-"
        r"[0-9]{8}T[0-9]{6}Z-page-([0-9]{4})\.json",
        member_name,
    )
    if match is None:
        raise ValueError("retained page path must be canonical")
    page_number = int(match.group(1))
    if expected_page_number is not None and page_number != expected_page_number:
        raise ValueError("retained page order mismatch")
    prefix = _RETAINED_ENDPOINT + "?"
    if not source_url.startswith(prefix):
        raise ValueError("retained page endpoint mismatch")
    parts = source_url.removeprefix(prefix).split("&")
    if len(parts) not in (4, 5):
        raise ValueError("retained page query mismatch")
    expected_keys = ("symbol", "startTime", "endTime", "limit") + (
        ("fromId",) if len(parts) == 5 else ()
    )
    pairs = tuple(part.split("=", 1) for part in parts)
    if any(len(pair) != 2 for pair in pairs) or tuple(
        pair[0] for pair in pairs
    ) != expected_keys:
        raise ValueError("retained page query must use canonical order")
    parameters = {key: value for key, value in pairs}
    if parameters["symbol"] != _SYMBOL or parameters["limit"] != "1000":
        raise ValueError("retained page query identity mismatch")
    try:
        start = _canonical_integer(parameters["startTime"])
        end = _canonical_integer(parameters["endTime"])
        from_id = (
            _canonical_integer(parameters["fromId"])
            if "fromId" in parameters
            else None
        )
    except ValueError as error:
        raise ValueError("retained page query values must be canonical") from error
    return BinanceUsdmKoruRetainedAggregateTradesPageV1(
        member_name=member_name,
        content_sha256=_content_hash("page sha256", entry.get("sha256")),
        source_url=source_url,
        request_start_time_milliseconds=start,
        request_end_time_milliseconds=end,
        page_number=page_number,
        row_count=entry["row_count"],  # type: ignore[arg-type]
        from_aggregate_trade_id=from_id,
    )


def _rows_from_raw_pages(
    pages: tuple[BinanceUsdmKoruRetainedAggregateTradesPageV1, ...],
    raw_page_bytes: tuple[bytes, ...],
) -> tuple[_ParsedRow, ...]:
    if (
        type(raw_page_bytes) is not tuple
        or len(raw_page_bytes) != len(pages)
        or any(type(value) is not bytes for value in raw_page_bytes)
    ):
        raise ValueError("ordered retained page bytes must be exact")
    rows: list[_ParsedRow] = []
    expected_keys = ("T", "a", "f", "l", "m", "nq", "p", "q")
    for page, raw_bytes in zip(pages, raw_page_bytes, strict=True):
        if _sha256(raw_bytes) != page.content_sha256:
            raise ValueError("retained page hash mismatch")
        try:
            value = json.loads(raw_bytes, object_pairs_hook=_json_object)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            raise ValueError("retained page must be exact JSON") from error
        if (
            type(value) is not list
            or len(value) != page.row_count
            or not value
            or json.dumps(
                value,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
            != raw_bytes
        ):
            raise ValueError("retained page JSON must be canonical and nonempty")
        page_rows: list[_ParsedRow] = []
        for row_number, item in enumerate(value, len(rows) + 1):
            if type(item) is not dict or tuple(item) != expected_keys:
                raise ValueError("retained aggTrade JSON schema mismatch")
            if (
                type(item["a"]) is not int
                or type(item["f"]) is not int
                or type(item["l"]) is not int
                or type(item["T"]) is not int
                or type(item["m"]) is not bool
                or type(item["nq"]) is not str
                or type(item["p"]) is not str
                or type(item["q"]) is not str
            ):
                raise ValueError("retained aggTrade JSON value types mismatch")
            if _DECIMAL.fullmatch(item["nq"]) is None:
                raise ValueError("retained nq must be a canonical decimal")
            row = _parse_row(
                [
                    str(item["a"]),
                    item["p"],
                    item["q"],
                    str(item["f"]),
                    str(item["l"]),
                    str(item["T"]),
                    "true" if item["m"] else "false",
                ],
                row_number,
            )
            if not (
                page.request_start_time_milliseconds
                <= row.transaction_time_milliseconds
                <= page.request_end_time_milliseconds
            ):
                raise ValueError("retained row falls outside exact request window")
            page_rows.append(row)
        if page.from_aggregate_trade_id is not None and (
            page_rows[0].aggregate_trade_id != page.from_aggregate_trade_id
        ):
            raise ValueError("retained page fromId does not bind its first row")
        rows.extend(page_rows)
    validated = _validated_rows(
        [list(row.exact_row) for row in rows],
        UtcInstant(_RETAINED_COVERAGE_START_MS * 1_000_000),
        UtcInstant(_RETAINED_COVERAGE_END_MS * 1_000_000),
    )
    if validated != tuple(rows):
        raise ValueError("retained page rows do not replay exactly")
    return validated


def _derived_csv_from_rows(rows: tuple[_ParsedRow, ...]) -> bytes:
    return (
        ",".join(_CSV_HEADER)
        + "\n"
        + "".join(",".join(row.exact_row) + "\n" for row in rows)
    ).encode()


def build_binance_usdm_koru_aggregate_trades_retained_rest_evidence_v1(
    authority: BinanceUsdmKoruRetainedAggregateTradesAuthorityV1,
    derived_csv_bytes: bytes,
) -> tuple[bytes, bytes]:
    trusted = _trusted_authority(authority)
    if (
        trusted is None
        or type(derived_csv_bytes) is not bytes
        or _sha256(derived_csv_bytes) != trusted.derived_csv_sha256
    ):
        raise ValueError("derived CSV must exactly match retained authority")
    output = io.BytesIO()
    member = ZipInfo(trusted.derived_csv_member_name, (1980, 1, 1, 0, 0, 0))
    member.compress_type = ZIP_DEFLATED
    member.external_attr = 0o100644 << 16
    with ZipFile(output, "w") as archive:
        archive.writestr(
            member,
            derived_csv_bytes,
            compress_type=ZIP_DEFLATED,
            compresslevel=9,
        )
    archive_bytes = output.getvalue()
    archive_name = trusted.derived_csv_member_name.removesuffix(".csv") + ".zip"
    checksum_bytes = f"{_sha256(archive_bytes)[7:]}  {archive_name}\n".encode()
    return archive_bytes, checksum_bytes


def _reconstruct_retained_authority(
    execution_manifest_bytes: bytes,
    raw_page_bytes: tuple[bytes, ...],
    derived_csv_bytes: bytes,
    archive_bytes: bytes,
    checksum_bytes: bytes,
) -> BinanceUsdmKoruRetainedAggregateTradesAuthorityV1:
    manifest = _execution_manifest(execution_manifest_bytes)
    if not _exact_mapping(
        manifest.get("holdout_protection"),
        {
            "full_2026_08_24_daily_archive_downloaded": False,
            "policy": "No request, retained row, or archive may address this instant or later",
            "rest_end_time_inclusive": _RETAINED_COVERAGE_END_MS - 1,
            "start_utc_inclusive": "2026-08-24T11:00:00.000Z",
        },
    ):
        raise ValueError("execution manifest holdout protection mismatch")
    if manifest.get("missing_intervals") != [
        {
            "dataset": "aggTrades",
            "end_utc_exclusive": "2026-08-24T06:34:20.640Z",
            "reason": "Binance public aggTrades REST rejected older requests with code -4166; no archive or alternate feed was used for 2026-08-24",
            "start_utc_inclusive": "2026-08-24T00:00:00.000Z",
        }
    ]:
        raise ValueError("execution manifest missing prefix mismatch")
    generated_at = _iso_milliseconds(manifest.get("generated_at_utc"))
    if manifest.get("generated_at_basis") != (
        "frozen base manifest generated_at_utc used as a deterministic offline regeneration marker"
    ):
        raise ValueError("execution manifest generated-at basis mismatch")
    files = _manifest_files(manifest)
    page_entries: list[dict[str, object]] = []
    for entry in files:
        path = entry.get("path")
        if (
            type(path) is str
            and path.startswith(_RETAINED_RAW_PATH_PREFIX)
            and entry.get("status") == "canonical_rest_response"
        ):
            page_entries.append(entry)
    pages = tuple(
        _page_from_manifest_entry(entry, None) for entry in page_entries
    )
    rows = _rows_from_raw_pages(pages, raw_page_bytes)
    derived_expected = _derived_csv_from_rows(rows)
    if derived_csv_bytes != derived_expected:
        raise ValueError("derived CSV does not exactly reconstruct raw pages")
    derived_path = _RETAINED_RAW_PATH_PREFIX + _RETAINED_DERIVED_CSV_NAME
    derived_entry = _manifest_file(
        files, derived_path, "rest_derived_standard_schema"
    )
    if (
        derived_entry["sha256"] != _sha256(derived_csv_bytes)
        or derived_entry["size_bytes"] != len(derived_csv_bytes)
        or derived_entry["row_count"] != len(rows)
    ):
        raise ValueError("derived CSV manifest binding mismatch")
    availability_authority = _trusted_availability_authority(
        BINANCE_USDM_KORU_AGGREGATE_TRADE_AVAILABILITY_AUTHORITY_V1
    )
    if availability_authority is None:
        raise ValueError("retained availability authority reconstruction mismatch")
    authority = BinanceUsdmKoruRetainedAggregateTradesAuthorityV1(
        execution_manifest_path=_RETAINED_EXECUTION_MANIFEST_PATH,
        execution_manifest_file_sha256=_sha256(execution_manifest_bytes),
        execution_manifest_identity=manifest["manifest_sha256"],  # type: ignore[arg-type]
        execution_manifest_generated_at_epoch_nanoseconds=generated_at * 1_000_000,
        pages=pages,
        selected_coverage_start=UtcInstant(
            _RETAINED_COVERAGE_START_MS * 1_000_000
        ),
        selected_coverage_end_exclusive=UtcInstant(
            _RETAINED_COVERAGE_END_MS * 1_000_000
        ),
        declared_missing_prefix_start=UtcInstant(
            _RETAINED_DAY_START_MS * 1_000_000
        ),
        declared_missing_prefix_end_exclusive=UtcInstant(
            _RETAINED_COVERAGE_START_MS * 1_000_000
        ),
        availability_authority=availability_authority,
        derived_csv_member_name=_RETAINED_DERIVED_CSV_NAME,
        derived_csv_sha256=_sha256(derived_csv_bytes),
        derived_csv_schema_identity=_RETAINED_CSV_SCHEMA_IDENTITY,
    )
    expected_archive, expected_checksum = (
        build_binance_usdm_koru_aggregate_trades_retained_rest_evidence_v1(
            authority, derived_csv_bytes
        )
    )
    if archive_bytes != expected_archive or checksum_bytes != expected_checksum:
        raise ValueError("derived ZIP/checksum must be deterministic")
    archive_name = authority.derived_csv_member_name.removesuffix(".csv") + ".zip"
    archive_entry = _manifest_file(
        files, _RETAINED_RAW_PATH_PREFIX + archive_name, "rest_derived_standard_schema"
    )
    checksum_entry = _manifest_file(
        files,
        _RETAINED_RAW_PATH_PREFIX + archive_name + ".CHECKSUM",
        "locally_generated_checksum",
    )
    if (
        archive_entry["sha256"] != _sha256(archive_bytes)
        or archive_entry["size_bytes"] != len(archive_bytes)
        or archive_entry["row_count"] != len(rows)
        or checksum_entry["sha256"] != _sha256(checksum_bytes)
        or checksum_entry["size_bytes"] != len(checksum_bytes)
        or checksum_entry["row_count"] != len(rows)
    ):
        raise ValueError("derived archive manifest binding mismatch")
    datasets = manifest.get("datasets")
    try:
        retained = datasets["aggTrades"]["rest_2026_08_24"]  # type: ignore[index]
    except (KeyError, TypeError) as error:
        raise ValueError("execution manifest retained dataset missing") from error
    if not _exact_mapping(
        retained,
        {
            "covered_end_utc_exclusive": "2026-08-24T11:00:00.000Z",
            "covered_start_utc_inclusive": "2026-08-24T06:34:20.640Z",
            "max_aggregate_trade_id": rows[-1].aggregate_trade_id,
            "max_raw_trade_id": rows[-1].last_trade_id,
            "max_time_ms": rows[-1].transaction_time_milliseconds,
            "max_time_utc": datetime.fromtimestamp(
                rows[-1].transaction_time_milliseconds / 1000, tz=UTC
            ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4]
            + "Z",
            "min_aggregate_trade_id": rows[0].aggregate_trade_id,
            "min_raw_trade_id": rows[0].first_trade_id,
            "min_time_ms": rows[0].transaction_time_milliseconds,
            "min_time_utc": datetime.fromtimestamp(
                rows[0].transaction_time_milliseconds / 1000, tz=UTC
            ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-4]
            + "Z",
            "provenance": "REST-derived; not an official archive",
            "row_count": len(rows),
        },
    ):
        raise ValueError("execution manifest retained dataset mismatch")
    return authority


def _retained_member_keys(
    request: BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1,
) -> tuple[str, ...]:
    authority = request.authority
    if authority is None:
        raise ValueError("retained authority required")
    return tuple(
        sorted(
            (
                _RETAINED_AVAILABILITY_AUTHORITY_MEMBER_KEY,
                _RETAINED_EXECUTION_MANIFEST_MEMBER_KEY,
                *("retained/raw/" + page.member_name for page in authority.pages),
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


def _snapshot_bytes(
    snapshot: SourceSnapshot, member_keys: tuple[str, ...]
) -> tuple[bytes, ...]:
    try:
        with tarfile.open(fileobj=io.BytesIO(snapshot.archive_bytes), mode="r:gz") as archive:
            values = []
            for member_key in member_keys:
                extracted = archive.extractfile(member_key)
                if extracted is None:
                    raise ValueError
                values.append(extracted.read())
        return tuple(values)
    except (KeyError, OSError, tarfile.TarError, ValueError) as error:
        raise ValueError("source snapshot member unavailable") from error


def _snapshot_matches_request(
    request: BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1,
    snapshot: SourceSnapshot,
) -> bool:
    prefix = "derived/" if request.authority is not None else "archive/"
    archive_key = prefix + request.archive_name
    checksum_key = prefix + request.checksum_name
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
        or any(
            member.acquired_at_epoch_nanoseconds
            != request.acquired_at_epoch_nanoseconds
            or member.mode != "0644"
            or member.content_hash != member.declared_sha256
            for member in snapshot.members
        )
    ):
        return False
    try:
        archive_member = _snapshot_member(snapshot, archive_key)
        checksum_member = _snapshot_member(snapshot, checksum_key)
    except StopIteration:
        return False
    if (
        archive_member.content_hash != request.expected_archive_sha256
        or checksum_member.content_hash != request.expected_checksum_sha256
    ):
        return False
    retained_keys = (
        (
            _RETAINED_AVAILABILITY_AUTHORITY_MEMBER_KEY,
            _RETAINED_EXECUTION_MANIFEST_MEMBER_KEY,
            *("retained/raw/" + page.member_name for page in request.authority.pages),
            _RETAINED_DERIVED_CSV_MEMBER_KEY,
        )
        if request.authority is not None
        else ()
    )
    try:
        values = _snapshot_bytes(
            snapshot, (archive_key, checksum_key, *retained_keys)
        )
        archive, checksum = values[:2]
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
        if values[2] != _availability_authority_bytes():
            return False
        reconstructed = _reconstruct_retained_authority(
            values[3],
            values[4:-1],
            values[-1],
            archive,
            checksum,
        )
        return (
            reconstructed.to_canonical_dict()
            == request.authority.to_canonical_dict()
        )
    except (KeyError, OSError, RuntimeError, StopIteration, ValueError):
        return False


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1:
    request: BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1
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
            raise ValueError("capture result must bind exact verified KORU source evidence")
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("development-only qualification flags must remain false")
        object.__setattr__(self, "request", trusted)

    @property
    def capture_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_aggregate_trades_source_bounded_capture_result_v1",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request.to_canonical_dict(),
            "request_hash": self.request.request_hash,
            "snapshot": self.snapshot.to_canonical_dict(),
            "source_snapshot_hash": canonical_sha256(
                self.snapshot.to_canonical_dict()
            ),
            "archive_attempts": self.archive_attempts,
            "checksum_attempts": self.checksum_attempts,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


def _trusted_capture(
    value: object,
) -> BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1 | None:
    if type(value) is not BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1:
        return None
    try:
        rebuilt = BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1(
            value.request,
            value.snapshot,
            value.archive_attempts,
            value.checksum_attempts,
            value.decision_grade_eligible,
            value.deployment_authorized,
        )
        if rebuilt.to_canonical_dict() != value.to_canonical_dict():
            return None
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruAggregateTradesSourceBoundedCaptureOutcomeV1:
    result: BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1 | None = None
    failure: BinanceUsdmKoruAggregateTradesSourceBoundedFailureV1 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")
        if self.result is not None and _trusted_capture(self.result) is None:
            raise ValueError("capture outcome result is not canonical")
        if (
            self.failure is not None
            and type(self.failure)
            is not BinanceUsdmKoruAggregateTradesSourceBoundedFailureV1
        ):
            raise TypeError("capture outcome failure must be exact")


def _fetch(
    url: str, fetch: FetchBytes
) -> tuple[
    bytes | None,
    int,
    BinanceUsdmKoruAggregateTradesSourceBoundedFailureV1 | None,
]:
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = fetch(url)
        except (ConnectionError, OSError, RuntimeError, TimeoutError):
            response = None
        if response is None:
            if attempt == _MAX_ATTEMPTS:
                return None, attempt, _failure(
                    BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.PROVIDER_UNAVAILABLE,
                    url,
                )
            continue
        if (
            type(response) is not tuple
            or len(response) != 2
            or type(response[0]) is not int
            or type(response[1]) is not bytes
        ):
            return None, attempt, _failure(
                BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.CONFIGURATION_INVALID,
                url,
            )
        status, body = response
        if status == 200:
            return body, attempt, None
        if status in (401, 403):
            return None, attempt, _failure(
                BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.AUTHENTICATION_REJECTED,
                url,
            )
        if status == 429:
            if attempt < _MAX_ATTEMPTS:
                continue
            return None, attempt, _failure(
                BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.RATE_LIMIT_EXHAUSTED,
                url,
            )
        if 500 <= status <= 599:
            if attempt < _MAX_ATTEMPTS:
                continue
            return None, attempt, _failure(
                BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.PROVIDER_UNAVAILABLE,
                url,
            )
        return None, attempt, _failure(
            (
                BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.DATA_GAP_DETECTED
                if status == 404
                else BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH
            ),
            url,
        )
    raise AssertionError("unreachable")


def capture_binance_usdm_koru_aggregate_trades_source_bounded_v1(
    request: BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1,
    fetch: FetchBytes,
) -> BinanceUsdmKoruAggregateTradesSourceBoundedCaptureOutcomeV1:
    trusted = _trusted_request(request)
    if trusted is None or trusted.authority is not None or not callable(fetch):
        return BinanceUsdmKoruAggregateTradesSourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.CONFIGURATION_INVALID
            )
        )
    archive_url, checksum_url = trusted.urls
    archive, archive_attempts, archive_failure = _fetch(archive_url, fetch)
    checksum, checksum_attempts, checksum_failure = _fetch(checksum_url, fetch)
    if archive is not None and _sha256(archive) != trusted.expected_archive_sha256:
        archive_failure = _failure(
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH,
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
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH,
            checksum_url,
        )
    failures = tuple(
        failure
        for failure in (archive_failure, checksum_failure)
        if failure is not None
    )
    if failures:
        precedence = tuple(BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1)
        return BinanceUsdmKoruAggregateTradesSourceBoundedCaptureOutcomeV1(
            failure=min(
                failures, key=lambda failure: precedence.index(failure.code)
            )
        )
    if archive is None or checksum is None:
        return BinanceUsdmKoruAggregateTradesSourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.CONFIGURATION_INVALID
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
        return BinanceUsdmKoruAggregateTradesSourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SNAPSHOT_INVALID
            )
        )
    try:
        result = BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1(
            trusted,
            frozen.snapshot,
            archive_attempts,
            checksum_attempts,
        )
    except (TypeError, ValueError):
        return BinanceUsdmKoruAggregateTradesSourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SNAPSHOT_INVALID
            )
        )
    return BinanceUsdmKoruAggregateTradesSourceBoundedCaptureOutcomeV1(result=result)


def capture_binance_usdm_koru_aggregate_trades_from_retained_rest_v1(
    request: BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1,
    execution_manifest_bytes: bytes,
    raw_page_bytes: tuple[bytes, ...],
    derived_csv_bytes: bytes,
    archive_bytes: bytes,
    checksum_bytes: bytes,
) -> BinanceUsdmKoruAggregateTradesSourceBoundedCaptureOutcomeV1:
    trusted = _trusted_request(request)
    if trusted is None or trusted.authority is None:
        return BinanceUsdmKoruAggregateTradesSourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.CONFIGURATION_INVALID
            )
        )
    try:
        reconstructed = _reconstruct_retained_authority(
            execution_manifest_bytes,
            raw_page_bytes,
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
        return BinanceUsdmKoruAggregateTradesSourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH,
                "retained_authority",
            )
        )
    availability_authority_bytes = _availability_authority_bytes()
    members = [
        RawSourceMember(
            _RETAINED_AVAILABILITY_AUTHORITY_MEMBER_KEY,
            availability_authority_bytes,
            "0644",
            trusted.acquired_at_epoch_nanoseconds,
            _sha256(availability_authority_bytes),
        ),
        RawSourceMember(
            _RETAINED_EXECUTION_MANIFEST_MEMBER_KEY,
            execution_manifest_bytes,
            "0644",
            trusted.acquired_at_epoch_nanoseconds,
            reconstructed.execution_manifest_file_sha256,
        ),
        *(
            RawSourceMember(
                "retained/raw/" + page.member_name,
                value,
                "0644",
                trusted.acquired_at_epoch_nanoseconds,
                page.content_sha256,
            )
            for page, value in zip(
                reconstructed.pages, raw_page_bytes, strict=True
            )
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
    ]
    frozen = freeze_source_snapshot(members=members, provenance=_provenance(trusted))
    if frozen.snapshot is None:
        return BinanceUsdmKoruAggregateTradesSourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SNAPSHOT_INVALID
            )
        )
    try:
        result = BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1(
            trusted, frozen.snapshot, 1, 1
        )
    except (TypeError, ValueError):
        return BinanceUsdmKoruAggregateTradesSourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SNAPSHOT_INVALID
            )
        )
    return BinanceUsdmKoruAggregateTradesSourceBoundedCaptureOutcomeV1(result=result)


class _NormalizationError(ValueError):
    def __init__(
        self,
        code: BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1,
        subject: str,
        row_number: int | None = None,
    ) -> None:
        super().__init__(subject)
        self.code = code
        self.subject = subject
        self.row_number = row_number


@dataclass(frozen=True, slots=True)
class _ParsedRow:
    aggregate_trade_id: int
    price: str
    quantity: str
    first_trade_id: int
    last_trade_id: int
    transaction_time_milliseconds: int
    is_buyer_maker: bool
    exact_row: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1:
    previous_aggregate_trade_id: int
    current_aggregate_trade_id: int
    previous_last_trade_id: int
    current_first_trade_id: int
    missing_first_trade_id: int
    missing_last_trade_id: int
    missing_trade_count: int
    previous_transaction_time_milliseconds: int
    current_transaction_time_milliseconds: int
    gap_hash: str = field(init=False)

    def __post_init__(self) -> None:
        values = (
            self.previous_aggregate_trade_id,
            self.current_aggregate_trade_id,
            self.previous_last_trade_id,
            self.current_first_trade_id,
            self.missing_first_trade_id,
            self.missing_last_trade_id,
            self.missing_trade_count,
            self.previous_transaction_time_milliseconds,
            self.current_transaction_time_milliseconds,
        )
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError("raw-ID gap evidence values must be exact non-negative integers")
        if (
            self.current_aggregate_trade_id != self.previous_aggregate_trade_id + 1
            or self.current_first_trade_id <= self.previous_last_trade_id + 1
            or self.missing_first_trade_id != self.previous_last_trade_id + 1
            or self.missing_last_trade_id != self.current_first_trade_id - 1
            or self.missing_trade_count
            != self.current_first_trade_id - self.previous_last_trade_id - 1
            or self.current_transaction_time_milliseconds
            < self.previous_transaction_time_milliseconds
        ):
            raise ValueError("raw-ID gap evidence does not bind an exact adjacent gap")
        object.__setattr__(self, "gap_hash", canonical_sha256(self._body()))

    def _body(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_aggregate_trade_raw_id_gap_evidence_v1",
            "schema_version": _SCHEMA_VERSION,
            "previous_aggregate_trade_id": self.previous_aggregate_trade_id,
            "current_aggregate_trade_id": self.current_aggregate_trade_id,
            "previous_last_trade_id": self.previous_last_trade_id,
            "current_first_trade_id": self.current_first_trade_id,
            "missing_first_trade_id": self.missing_first_trade_id,
            "missing_last_trade_id": self.missing_last_trade_id,
            "missing_trade_count": self.missing_trade_count,
            "previous_transaction_time_milliseconds": self.previous_transaction_time_milliseconds,
            "current_transaction_time_milliseconds": self.current_transaction_time_milliseconds,
        }

    def to_canonical_dict(self) -> dict[str, object]:
        return {**self._body(), "gap_hash": self.gap_hash}


@dataclass(frozen=True, slots=True)
class _ReconstructedSource:
    requested_day_start: UtcInstant
    requested_day_end_exclusive: UtcInstant
    coverage_start: UtcInstant
    coverage_end_exclusive: UtcInstant
    first_aggregate_trade_id: int
    last_aggregate_trade_id: int
    source_member_hash: str
    events: tuple[MarketEvent, ...]
    raw_id_gaps: tuple[BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1, ...]


def _canonical_integer(value: str) -> int:
    if _INTEGER.fullmatch(value) is None:
        raise ValueError("non-canonical integer")
    try:
        return int(value)
    except ValueError as error:
        raise ValueError("non-canonical integer") from error


def _canonical_positive_decimal(value: str) -> str:
    if _DECIMAL.fullmatch(value) is None:
        raise ValueError("non-canonical decimal")
    whole, fraction = value.split(".")
    try:
        whole_units = int(whole)
    except ValueError as error:
        raise ValueError("non-canonical decimal") from error
    if whole_units == 0 and not any(character != "0" for character in fraction):
        raise ValueError("decimal must be positive")
    return value


def _read_retained_csv(
    capture: BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1,
) -> bytes:
    request = capture.request
    prefix = "derived/" if request.authority is not None else "archive/"
    archive_key = prefix + request.archive_name
    checksum_key = prefix + request.checksum_name
    member_keys = (
        (archive_key, checksum_key, _RETAINED_DERIVED_CSV_MEMBER_KEY)
        if request.authority is not None
        else (archive_key, checksum_key)
    )
    try:
        values = _snapshot_bytes(capture.snapshot, member_keys)
        archive, checksum = values[:2]
    except ValueError as error:
        raise _NormalizationError(
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "snapshot_member",
        ) from error
    if (
        _sha256(archive) != request.expected_archive_sha256
        or _sha256(checksum) != request.expected_checksum_sha256
        or checksum
        != f"{request.expected_archive_sha256[7:]}  {request.archive_name}\n".encode()
    ):
        raise _NormalizationError(
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH,
            "checksum",
        )
    try:
        with ZipFile(io.BytesIO(archive)) as zip_file:
            if zip_file.namelist() != [request.csv_name]:
                raise _NormalizationError(
                    BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
                    "zip_member",
                )
            csv_bytes = zip_file.read(request.csv_name)
            if request.authority is not None:
                retained_csv = values[2]
                if (
                    csv_bytes != retained_csv
                    or _sha256(retained_csv)
                    != request.authority.derived_csv_sha256
                ):
                    raise _NormalizationError(
                        BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH,
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
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "zip",
        ) from error


def _is_csv_header_like(row: tuple[str, ...], header: tuple[str, ...]) -> bool:
    return any(value in header for value in row)


def _csv_rows(
    csv_bytes: bytes,
    header: tuple[str, ...] | None = None,
    *,
    optional_header: bool = False,
) -> list[list[str]]:
    if not csv_bytes or b"\r" in csv_bytes or not csv_bytes.endswith(b"\n"):
        raise _NormalizationError(
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "csv_encoding",
        )
    try:
        text = csv_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise _NormalizationError(
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "csv_encoding",
        ) from error
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except csv.Error as error:
        raise _NormalizationError(
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "csv",
        ) from error
    header_present = False
    if header is not None:
        first_row = tuple(rows[0]) if rows else ()
        header_present = first_row == header
        if header_present:
            rows = rows[1:]
        elif not optional_header or _is_csv_header_like(first_row, header):
            raise _NormalizationError(
                BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
                "csv_header",
            )
    if not rows:
        raise _NormalizationError(
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
            "row_count",
        )
    canonical = "".join(",".join(row) + "\n" for row in rows).encode()
    if header_present:
        canonical = (",".join(header) + "\n").encode() + canonical
    if canonical != csv_bytes:
        raise _NormalizationError(
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "csv_grammar",
        )
    return rows


def _parse_row(row: list[str], row_number: int) -> _ParsedRow:
    if len(row) != 7:
        raise _NormalizationError(
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "csv_columns",
            row_number,
        )
    try:
        aggregate_trade_id = _canonical_integer(row[0])
        price = _canonical_positive_decimal(row[1])
        quantity = _canonical_positive_decimal(row[2])
        first_trade_id = _canonical_integer(row[3])
        last_trade_id = _canonical_integer(row[4])
        transaction_time = _canonical_integer(row[5])
        if row[6] not in ("true", "false"):
            raise ValueError("non-canonical boolean")
    except (TypeError, ValueError) as error:
        code = (
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH
            if _is_csv_header_like(tuple(row), _CSV_HEADER)
            else BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.NORMALIZATION_FAILED
        )
        raise _NormalizationError(code, "row_value", row_number) from error
    if first_trade_id > last_trade_id:
        raise _NormalizationError(
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
            "trade_id_range",
            row_number,
        )
    return _ParsedRow(
        aggregate_trade_id=aggregate_trade_id,
        price=price,
        quantity=quantity,
        first_trade_id=first_trade_id,
        last_trade_id=last_trade_id,
        transaction_time_milliseconds=transaction_time,
        is_buyer_maker=row[6] == "true",
        exact_row=tuple(row),
    )


def _validated_rows(
    rows: list[list[str]], requested_start: UtcInstant, requested_end: UtcInstant
) -> tuple[_ParsedRow, ...]:
    day_start_ms = requested_start.epoch_nanoseconds // 1_000_000
    day_end_ms = requested_end.epoch_nanoseconds // 1_000_000
    parsed: list[_ParsedRow] = []
    observed: dict[int, tuple[str, ...]] = {}
    previous: _ParsedRow | None = None
    for row_number, row in enumerate(rows, 1):
        current = _parse_row(row, row_number)
        duplicate = observed.get(current.aggregate_trade_id)
        if duplicate is not None:
            raise _NormalizationError(
                BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.DUPLICATE_OR_CONFLICT,
                (
                    "duplicate_aggregate_trade"
                    if duplicate == current.exact_row
                    else "conflicting_aggregate_trade"
                ),
                row_number,
            )
        observed[current.aggregate_trade_id] = current.exact_row
        if previous is not None:
            if current.aggregate_trade_id > previous.aggregate_trade_id + 1:
                raise _NormalizationError(
                    BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
                    "aggregate_trade_id_gap",
                    row_number,
                )
            if current.aggregate_trade_id <= previous.aggregate_trade_id:
                raise _NormalizationError(
                    BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.ORDER_VIOLATION,
                    "aggregate_trade_id_order",
                    row_number,
                )
            if current.first_trade_id <= previous.last_trade_id:
                raise _NormalizationError(
                    BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
                    "trade_id_range_overlap",
                    row_number,
                )
            if (
                current.transaction_time_milliseconds
                < previous.transaction_time_milliseconds
            ):
                raise _NormalizationError(
                    BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.ORDER_VIOLATION,
                    "transaction_time_order",
                    row_number,
                )
        if not (
            day_start_ms
            <= current.transaction_time_milliseconds
            < day_end_ms
        ):
            raise _NormalizationError(
                BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
                "transaction_time_date",
                row_number,
            )
        parsed.append(current)
        previous = current
    return tuple(parsed)


def _raw_id_gaps(
    rows: tuple[_ParsedRow, ...],
) -> tuple[BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1, ...]:
    return tuple(
        BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1(
            previous_aggregate_trade_id=previous.aggregate_trade_id,
            current_aggregate_trade_id=current.aggregate_trade_id,
            previous_last_trade_id=previous.last_trade_id,
            current_first_trade_id=current.first_trade_id,
            missing_first_trade_id=previous.last_trade_id + 1,
            missing_last_trade_id=current.first_trade_id - 1,
            missing_trade_count=current.first_trade_id - previous.last_trade_id - 1,
            previous_transaction_time_milliseconds=previous.transaction_time_milliseconds,
            current_transaction_time_milliseconds=current.transaction_time_milliseconds,
        )
        for previous, current in pairwise(rows)
        if current.first_trade_id > previous.last_trade_id + 1
    )


def _event_from_row(
    capture: BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1,
    row: _ParsedRow,
    source_index: int,
    source_member_hash: str,
) -> MarketEvent:
    request = capture.request
    prefix = "derived/" if request.authority is not None else "archive/"
    archive_key = prefix + request.archive_name
    checksum_key = prefix + request.checksum_name
    archive_member = _snapshot_member(capture.snapshot, archive_key)
    checksum_member = _snapshot_member(capture.snapshot, checksum_key)
    snapshot_hash = canonical_sha256(capture.snapshot.to_canonical_dict())
    identity = {
        "type": "binance_usdm_koru_aggregate_trade_event_identity_v1",
        "schema_version": _SCHEMA_VERSION,
        "snapshot_id": capture.snapshot.snapshot_id,
        "aggregate_trade_id": row.aggregate_trade_id,
    }
    authority = (
        _trusted_authority(request.authority)
        if request.authority is not None
        else None
    )
    if request.authority is not None and authority is None:
        raise ValueError("retained event authority must be exact")
    if authority is not None:
        availability_authority = authority.availability_authority
        identity["retained_authority_hash"] = authority.authority_hash
        identity["availability_authority_ref"] = availability_authority.authority_ref
        identity["availability_authority_digest"] = (
            availability_authority.authority_digest
        )
    payload = {
        "price_purpose": "execution_reference",
        "aggregate_trade_id": row.aggregate_trade_id,
        "first_trade_id": row.first_trade_id,
        "last_trade_id": row.last_trade_id,
        "price": row.price,
        "quantity": row.quantity,
        "is_buyer_maker": row.is_buyer_maker,
        "transaction_time_milliseconds": row.transaction_time_milliseconds,
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
        "archive_available_at_epoch_nanoseconds": request.archive_available_at_epoch_nanoseconds,
        "acquired_at_epoch_nanoseconds": request.acquired_at_epoch_nanoseconds,
    }
    retained_keys: set[str] = set()
    if authority is not None:
        availability_authority = authority.availability_authority
        payload.update(
            {
                "source_mode": _RETAINED_SOURCE_MODE,
                "retained_authority_hash": authority.authority_hash,
                "execution_manifest_identity": authority.execution_manifest_identity,
                "execution_manifest_file_sha256": authority.execution_manifest_file_sha256,
                "availability_authority_ref": availability_authority.authority_ref,
                "availability_authority_digest": availability_authority.authority_digest,
                "provider_archive_claim": False,
                "execution_manifest_generated_at_epoch_nanoseconds": authority.execution_manifest_generated_at_epoch_nanoseconds,
                "local_retained_acquired_at_epoch_nanoseconds": request.acquired_at_epoch_nanoseconds,
                "development_only": True,
            }
        )
        retained_keys = {
            "source_mode",
            "retained_authority_hash",
            "execution_manifest_identity",
            "execution_manifest_file_sha256",
            "availability_authority_ref",
            "availability_authority_digest",
            "provider_archive_claim",
            "execution_manifest_generated_at_epoch_nanoseconds",
            "local_retained_acquired_at_epoch_nanoseconds",
            "development_only",
        }
    if frozenset(payload) != _EVENT_PAYLOAD_KEYS | retained_keys:
        raise AssertionError("event payload lineage is incomplete")
    return MarketEvent(
        event_id="binance-usdm-koru-aggregate-trade-v1:"
        + canonical_sha256(identity),
        stream_key=_STREAM_KEY,
        event_type=_EVENT_TYPE,
        capability=_CAPABILITY,
        instrument_id=request.instrument_id,
        event_time=UtcInstant(row.transaction_time_milliseconds * 1_000_000),
        available_time=(
            UtcInstant(row.transaction_time_milliseconds * 1_000_000)
            if request.authority is not None
            else UtcInstant(request.archive_available_at_epoch_nanoseconds)
        ),
        phase=_PHASE,
        source_sequence=SourceSequence(source_index),
        revision_id=archive_member.content_hash,
        supersedes_revision_id=None,
        source_key=capture.snapshot.provenance.source_key,
        source_hash=archive_member.content_hash,
        payload=payload,
    )


def _reconstruct_retained_source(
    capture: BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1,
) -> _ReconstructedSource:
    csv_bytes = _read_retained_csv(capture)
    requested_start, requested_end = _date_bounds(capture.request.utc_date)
    authority = capture.request.authority
    rows = _validated_rows(
        _csv_rows(
            csv_bytes,
            _CSV_HEADER,
            optional_header=authority is None,
        ),
        authority.selected_coverage_start if authority is not None else requested_start,
        (
            authority.selected_coverage_end_exclusive
            if authority is not None
            else requested_end
        ),
    )
    source_member_hash = _sha256(csv_bytes)
    try:
        events = tuple(
            _event_from_row(capture, row, source_index, source_member_hash)
            for source_index, row in enumerate(rows)
        )
    except (TypeError, ValueError) as error:
        raise _NormalizationError(
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
            "market_event",
        ) from error
    return _ReconstructedSource(
        requested_day_start=requested_start,
        requested_day_end_exclusive=requested_end,
        coverage_start=(
            authority.selected_coverage_start
            if authority is not None
            else events[0].event_time
        ),
        coverage_end_exclusive=(
            authority.selected_coverage_end_exclusive
            if authority is not None
            else UtcInstant(events[-1].event_time.epoch_nanoseconds + 1)
        ),
        first_aggregate_trade_id=rows[0].aggregate_trade_id,
        last_aggregate_trade_id=rows[-1].aggregate_trade_id,
        source_member_hash=source_member_hash,
        events=events,
        raw_id_gaps=_raw_id_gaps(rows),
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationResultV1:
    capture: BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1
    source_snapshot_id: str
    source_snapshot_hash: str
    request_hash: str
    capture_hash: str
    requested_day_start: UtcInstant
    requested_day_end_exclusive: UtcInstant
    coverage_start: UtcInstant
    coverage_end_exclusive: UtcInstant
    prefix_gap_classification: str
    suffix_gap_classification: str
    internal_gap_classification: str
    row_count: int
    first_aggregate_trade_id: int
    last_aggregate_trade_id: int
    source_member_hash: str
    events: tuple[MarketEvent, ...]
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False
    raw_id_gaps: tuple[BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1, ...] = ()

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
            self.source_snapshot_id != trusted.snapshot.snapshot_id
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
            or self.prefix_gap_classification != _PREFIX_GAP_CLASSIFICATION
            or self.suffix_gap_classification != _SUFFIX_GAP_CLASSIFICATION
            or self.internal_gap_classification
            != (
                _RAW_ID_GAP_CLASSIFICATION
                if reconstructed.raw_id_gaps
                else _INTERNAL_GAP_CLASSIFICATION
            )
            or type(self.raw_id_gaps) is not tuple
            or any(
                type(gap) is not BinanceUsdmKoruAggregateTradeRawIdGapEvidenceV1
                for gap in self.raw_id_gaps
            )
            or self.raw_id_gaps != reconstructed.raw_id_gaps
            or [gap.to_canonical_dict() for gap in self.raw_id_gaps]
            != [gap.to_canonical_dict() for gap in reconstructed.raw_id_gaps]
            or type(self.events) is not tuple
            or any(type(event) is not MarketEvent for event in self.events)
            or self.events != expected_events
            or [event.to_canonical_dict() for event in self.events]
            != [event.to_canonical_dict() for event in expected_events]
            or type(self.row_count) is not int
            or self.row_count != len(expected_events)
            or type(self.first_aggregate_trade_id) is not int
            or self.first_aggregate_trade_id
            != reconstructed.first_aggregate_trade_id
            or type(self.last_aggregate_trade_id) is not int
            or self.last_aggregate_trade_id
            != reconstructed.last_aggregate_trade_id
            or self.source_member_hash != reconstructed.source_member_hash
        ):
            raise ValueError("normalization result fields do not exactly reconstruct source")
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("development-only qualification flags must remain false")

    @property
    def normalization_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        value: dict[str, object] = {
            "type": "binance_usdm_koru_aggregate_trades_source_bounded_normalization_result_v1",
            "schema_version": _SCHEMA_VERSION,
            "source_snapshot_id": self.source_snapshot_id,
            "source_snapshot_hash": self.source_snapshot_hash,
            "request_hash": self.request_hash,
            "capture_hash": self.capture_hash,
            "requested_day_start": self.requested_day_start.to_canonical_dict(),
            "requested_day_end_exclusive": self.requested_day_end_exclusive.to_canonical_dict(),
            "coverage_start": self.coverage_start.to_canonical_dict(),
            "coverage_end_exclusive": self.coverage_end_exclusive.to_canonical_dict(),
            "prefix_gap_classification": self.prefix_gap_classification,
            "suffix_gap_classification": self.suffix_gap_classification,
            "internal_gap_classification": self.internal_gap_classification,
            "row_count": self.row_count,
            "first_aggregate_trade_id": self.first_aggregate_trade_id,
            "last_aggregate_trade_id": self.last_aggregate_trade_id,
            "source_member_hash": self.source_member_hash,
            "events": [event.to_canonical_dict() for event in self.events],
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }
        if self.raw_id_gaps:
            value["raw_id_gaps"] = [
                gap.to_canonical_dict() for gap in self.raw_id_gaps
            ]
        return value


def _trusted_normalization_result(
    value: object,
) -> BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationResultV1 | None:
    if (
        type(value)
        is not BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationResultV1
    ):
        return None
    try:
        rebuilt = BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationResultV1(
            capture=value.capture,
            source_snapshot_id=value.source_snapshot_id,
            source_snapshot_hash=value.source_snapshot_hash,
            request_hash=value.request_hash,
            capture_hash=value.capture_hash,
            requested_day_start=value.requested_day_start,
            requested_day_end_exclusive=value.requested_day_end_exclusive,
            coverage_start=value.coverage_start,
            coverage_end_exclusive=value.coverage_end_exclusive,
            prefix_gap_classification=value.prefix_gap_classification,
            suffix_gap_classification=value.suffix_gap_classification,
            internal_gap_classification=value.internal_gap_classification,
            row_count=value.row_count,
            first_aggregate_trade_id=value.first_aggregate_trade_id,
            last_aggregate_trade_id=value.last_aggregate_trade_id,
            source_member_hash=value.source_member_hash,
            events=value.events,
            decision_grade_eligible=value.decision_grade_eligible,
            deployment_authorized=value.deployment_authorized,
            raw_id_gaps=value.raw_id_gaps,
        )
        if rebuilt.to_canonical_dict() != value.to_canonical_dict():
            return None
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationOutcomeV1:
    result: BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationResultV1 | None = None
    failure: BinanceUsdmKoruAggregateTradesSourceBoundedFailureV1 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")
        if self.result is not None and _trusted_normalization_result(self.result) is None:
            raise ValueError("normalization outcome result is not canonical")
        if (
            self.failure is not None
            and type(self.failure)
            is not BinanceUsdmKoruAggregateTradesSourceBoundedFailureV1
        ):
            raise TypeError("normalization outcome failure must be exact")


def _normalization_failure(
    code: BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1,
    subject: str,
    row_number: int | None = None,
) -> BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationOutcomeV1:
    return BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationOutcomeV1(
        failure=_failure(code, subject, row_number)
    )


def normalize_binance_usdm_koru_aggregate_trades_source_bounded_v1(
    capture: BinanceUsdmKoruAggregateTradesSourceBoundedCaptureResultV1,
) -> BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationOutcomeV1:
    trusted = _trusted_capture(capture)
    if trusted is None:
        return _normalization_failure(
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.CONFIGURATION_INVALID,
            "capture",
        )
    try:
        reconstructed = _reconstruct_retained_source(trusted)
        result = BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationResultV1(
            capture=trusted,
            source_snapshot_id=trusted.snapshot.snapshot_id,
            source_snapshot_hash=canonical_sha256(
                trusted.snapshot.to_canonical_dict()
            ),
            request_hash=trusted.request.request_hash,
            capture_hash=trusted.capture_hash,
            requested_day_start=reconstructed.requested_day_start,
            requested_day_end_exclusive=reconstructed.requested_day_end_exclusive,
            coverage_start=reconstructed.coverage_start,
            coverage_end_exclusive=reconstructed.coverage_end_exclusive,
            prefix_gap_classification=_PREFIX_GAP_CLASSIFICATION,
            suffix_gap_classification=_SUFFIX_GAP_CLASSIFICATION,
            internal_gap_classification=(
                _RAW_ID_GAP_CLASSIFICATION
                if reconstructed.raw_id_gaps
                else _INTERNAL_GAP_CLASSIFICATION
            ),
            row_count=len(reconstructed.events),
            first_aggregate_trade_id=reconstructed.first_aggregate_trade_id,
            last_aggregate_trade_id=reconstructed.last_aggregate_trade_id,
            source_member_hash=reconstructed.source_member_hash,
            events=reconstructed.events,
            raw_id_gaps=reconstructed.raw_id_gaps,
        )
    except _NormalizationError as error:
        return _normalization_failure(error.code, error.subject, error.row_number)
    except (TypeError, ValueError):
        return _normalization_failure(
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
            "normalization_result",
        )
    return BinanceUsdmKoruAggregateTradesSourceBoundedNormalizationOutcomeV1(
        result=result
    )
