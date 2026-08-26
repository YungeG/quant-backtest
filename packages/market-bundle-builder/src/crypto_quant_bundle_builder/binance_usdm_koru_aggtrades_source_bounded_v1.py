from __future__ import annotations

import csv
import hashlib
import io
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from itertools import pairwise
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
_INSTRUMENT = InstrumentId(
    VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual"
)
_POST_ADJUSTMENT_START = date(2026, 7, 15)
_EPOCH_DATE = date(1970, 1, 1)
_DAY_NANOSECONDS = 86_400_000_000_000
_BASE_URL = "https://data.binance.vision/data/futures/um/daily/aggTrades/KORUUSDT/"
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


def _provenance(
    request: BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1,
) -> SourceSnapshotProvenance:
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
        return (
            _BASE_URL + self.archive_name,
            _BASE_URL + self.checksum_name,
        )

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
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


def _snapshot_matches_request(
    request: BinanceUsdmKoruAggregateTradesSourceBoundedRequestV1,
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
    if trusted is None or not callable(fetch):
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
    archive_key = "archive/" + request.archive_name
    checksum_key = "archive/" + request.checksum_name
    try:
        archive = capture.snapshot.member_bytes(archive_key)
        checksum = capture.snapshot.member_bytes(checksum_key)
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
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "zip",
        ) from error


def _csv_rows(csv_bytes: bytes) -> list[list[str]]:
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
    if not rows:
        raise _NormalizationError(
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
            "row_count",
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
        is_header = row_number == 1
        if is_header:
            is_header = row[0] == "agg_trade_id"
        code = (
            BinanceUsdmKoruAggregateTradesSourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH
            if is_header
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
    archive_member, checksum_member = capture.snapshot.members
    archive_key = "archive/" + request.archive_name
    snapshot_hash = canonical_sha256(capture.snapshot.to_canonical_dict())
    identity = {
        "type": "binance_usdm_koru_aggregate_trade_event_identity_v1",
        "schema_version": _SCHEMA_VERSION,
        "snapshot_id": capture.snapshot.snapshot_id,
        "aggregate_trade_id": row.aggregate_trade_id,
    }
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
    if frozenset(payload) != _EVENT_PAYLOAD_KEYS:
        raise AssertionError("event payload lineage is incomplete")
    return MarketEvent(
        event_id="binance-usdm-koru-aggregate-trade-v1:"
        + canonical_sha256(identity),
        stream_key=_STREAM_KEY,
        event_type=_EVENT_TYPE,
        capability=_CAPABILITY,
        instrument_id=request.instrument_id,
        event_time=UtcInstant(row.transaction_time_milliseconds * 1_000_000),
        available_time=UtcInstant(request.archive_available_at_epoch_nanoseconds),
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
    rows = _validated_rows(_csv_rows(csv_bytes), requested_start, requested_end)
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
        coverage_start=events[0].event_time,
        coverage_end_exclusive=UtcInstant(
            events[-1].event_time.epoch_nanoseconds + 1
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
