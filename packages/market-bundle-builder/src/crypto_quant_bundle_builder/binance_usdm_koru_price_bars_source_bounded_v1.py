"""Bounded KORU mark/index price-bar capture and exact projection.

Captured provider bytes are authoritative only for their frozen date, hashes, and
availability receipt. Future dates require separately captured hashes and receipts.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from enum import Enum
from zipfile import BadZipFile, ZipFile

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
        return _csv_name(self.utc_date)

    @property
    def urls(self) -> tuple[str, str]:
        base_url = _base_url(self.source_kind)
        return (base_url + self.archive_name, base_url + self.checksum_name)

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
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
        )
        if rebuilt.to_canonical_dict() != value.to_canonical_dict():
            return None
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return rebuilt


def _provenance(
    request: BinanceUsdmKoruPriceBarsSourceBoundedRequestV1,
) -> SourceSnapshotProvenance:
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


def _snapshot_matches_request(
    request: BinanceUsdmKoruPriceBarsSourceBoundedRequestV1,
    snapshot: SourceSnapshot,
) -> bool:
    archive_key = "archive/" + request.archive_name
    checksum_key = "archive/" + request.checksum_name
    if (
        type(snapshot) is not SourceSnapshot
        or verify_source_snapshot(snapshot).snapshot is None
        or tuple(member.member_key for member in snapshot.members)
        != (archive_key, checksum_key)
        or snapshot.provenance != _provenance(request)
        or snapshot.decision_grade_eligible
        or snapshot.deployment_authorized
    ):
        return False
    archive_member, checksum_member = snapshot.members
    if (
        archive_member.content_hash != request.expected_archive_sha256
        or archive_member.declared_sha256 != request.expected_archive_sha256
        or checksum_member.content_hash != request.expected_checksum_sha256
        or checksum_member.declared_sha256 != request.expected_checksum_sha256
        or archive_member.acquired_at_epoch_nanoseconds
        != request.acquired_at_epoch_nanoseconds
        or checksum_member.acquired_at_epoch_nanoseconds
        != request.acquired_at_epoch_nanoseconds
        or archive_member.mode != "0644"
        or checksum_member.mode != "0644"
    ):
        return False
    try:
        archive = snapshot.member_bytes(archive_key)
        checksum = snapshot.member_bytes(checksum_key)
    except ValueError:
        return False
    return (
        _sha256(archive) == request.expected_archive_sha256
        and _sha256(checksum) == request.expected_checksum_sha256
        and checksum
        == f"{request.expected_archive_sha256[7:]}  {request.archive_name}\n".encode()
    )


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
    if trusted is None or not callable(fetch):
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


def _price_units(value: str) -> int:
    match = _PRICE.fullmatch(value)
    if match is None:
        raise ValueError("non-canonical price")
    fraction = match.group(1) or ""
    try:
        whole_units = int(value.partition(".")[0])
        fractional_units = int(fraction.ljust(8, "0") or "0")
    except ValueError as error:
        raise ValueError("non-canonical price") from error
    units = whole_units * 100_000_000 + fractional_units
    if units <= 0:
        raise ValueError("price must be positive")
    return units


def _read_retained_csv(
    capture: BinanceUsdmKoruPriceBarsSourceBoundedCaptureResultV1,
) -> bytes:
    request = capture.request
    archive_key = "archive/" + request.archive_name
    checksum_key = "archive/" + request.checksum_name
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
            return zip_file.read(request.csv_name)
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


def _csv_rows(csv_bytes: bytes) -> list[list[str]]:
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
    if not rows or tuple(rows[0]) != _CSV_HEADER:
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
    rows: list[list[str]], requested_start: UtcInstant, requested_end: UtcInstant
) -> tuple[_ParsedRow, ...]:
    day_start_ms = requested_start.epoch_nanoseconds // 1_000_000
    day_end_ms = requested_end.epoch_nanoseconds // 1_000_000
    parsed: list[_ParsedRow] = []
    observed: dict[int, tuple[str, ...]] = {}
    previous: _ParsedRow | None = None
    for row_number, row in enumerate(rows, 1):
        current = _parse_row(row, row_number)
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
    archive_member, checksum_member = capture.snapshot.members
    archive_key = "archive/" + request.archive_name
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
    if definition.point:
        payload["price_units"] = row.close_units
    expected_keys: frozenset[str] = _COMMON_PAYLOAD_KEYS | (
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
    rows = _validated_rows(_csv_rows(csv_bytes), requested_start, requested_end)
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
