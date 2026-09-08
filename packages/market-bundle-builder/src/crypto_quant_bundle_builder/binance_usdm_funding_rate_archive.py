from __future__ import annotations

import csv
import hashlib
import io
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from zipfile import BadZipFile, ZipFile

from crypto_quant_domain import (
    InstrumentId,
    SourceSequence,
    TimelinePhase,
    UtcInstant,
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
_ARCHIVE_NAME = "BTCUSDT-fundingRate-2020-01.zip"
_CHECKSUM_NAME = _ARCHIVE_NAME + ".CHECKSUM"
_BASE_URL = "https://data.binance.vision/data/futures/um/monthly/fundingRate/BTCUSDT/"
_ARCHIVE_URL = _BASE_URL + _ARCHIVE_NAME
_CHECKSUM_URL = _BASE_URL + _CHECKSUM_NAME
_SOURCE_KEY = "binance.public_data.futures.um.monthly.funding_rate.btcusdt.2020-01"
_MAX_ATTEMPTS = 3
_ACQUIRED_AT = 1_786_932_488_331_056_046
_ARCHIVE_HASH = "sha256:7f81b2f3694d13779e7e896b69d60cd61e9444d7b9f9e90df761935e1c1b76e2"
_CHECKSUM_HASH = "sha256:3274779c977a6d657722bac4cc9f965bb774c5ba38aad391eb47ef183ae46120"
_SNAPSHOT_ID = "sha256:8a42a791c9471a20f734d88660b37b7e967b8eabb6007078e625b220add11ebd"
_CONTENT_TREE_HASH = "sha256:d596329bda3338709134d3b02403fb38f4cfed555a1b40910f877b15fba6196e"
_PROVENANCE_HASH = "sha256:7abdd0a03f8e3b833595492707869700fd19c410a68cd74c1eb419759d3f6e73"
_REQUEST_HASH = "sha256:adaba188f07aab97b311e995f41d7e2b266e82baaeb5d3b416560e1fc98e29c7"
_CSV_NAME = "BTCUSDT-fundingRate-2020-01.csv"
_CSV_HEADER = ("calc_time", "funding_interval_hours", "last_funding_rate")
_ROW_COUNT = 93
_FIRST_NOMINAL_SLOT_MILLISECONDS = 1_577_836_800_000
_SLOT_MILLISECONDS = 28_800_000
_RATE_SCALE = 8
_RATE = re.compile(r"([+-]?)([0-9]+)(?:\.([0-9]+))?(?:[eE]([+-]?[0-9]+))?\Z")
_PHASE = TimelinePhase(0, "market_data")
_FUNDING_CAPABILITY = MarketBundleCapability("binance_usdm.funding-publications", 1)

FetchBytes = Callable[[str], tuple[int, bytes]]


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


@dataclass(frozen=True, slots=True)
class BinanceUsdmFundingRateArchiveRequest:
    instrument_id: InstrumentId
    acquired_at_epoch_nanoseconds: int

    def __post_init__(self) -> None:
        if type(self.instrument_id) is not InstrumentId or (
            self.instrument_id.venue.value != "binance_usdm"
            or self.instrument_id.stable_key != "btc-usdt-perpetual"
        ):
            raise ValueError("instrument_id must be exact BTCUSDT perpetual identity")
        if self.acquired_at_epoch_nanoseconds != _ACQUIRED_AT:
            raise ValueError("acquisition time must match the frozen source capture")

    @property
    def urls(self) -> tuple[str, str]:
        return (_ARCHIVE_URL, _CHECKSUM_URL)

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_funding_rate_archive_request",
            "schema_version": _SCHEMA_VERSION,
            "instrument_id": self.instrument_id.to_canonical_dict(),
            "symbol": "BTCUSDT",
            "utc_month": "2020-01",
            "archive_url": _ARCHIVE_URL,
            "checksum_url": _CHECKSUM_URL,
            "acquired_at_epoch_nanoseconds": self.acquired_at_epoch_nanoseconds,
        }


def _is_exact_request(value: object) -> bool:
    try:
        return (
            type(value) is BinanceUsdmFundingRateArchiveRequest
            and value.request_hash == _REQUEST_HASH
        )
    except (AttributeError, TypeError, ValueError):
        return False


class BinanceUsdmArchiveFailureCode(str, Enum):
    CONFIGURATION_INVALID = "configuration_invalid"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    AUTHENTICATION_REJECTED = "authentication_rejected"
    RATE_LIMIT_EXHAUSTED = "rate_limit_exhausted"
    SOURCE_SCHEMA_MISMATCH = "source_schema_mismatch"
    NORMALIZATION_FAILED = "normalization_failed"
    DATA_GAP_DETECTED = "data_gap_detected"


@dataclass(frozen=True, slots=True)
class BinanceUsdmArchiveFailure:
    code: BinanceUsdmArchiveFailureCode
    subject: str | None = None
    row_number: int | None = None

    @property
    def failure_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_archive_failure",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
            "row_number": self.row_number,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmArchiveCaptureResult:
    request: BinanceUsdmFundingRateArchiveRequest
    snapshot: SourceSnapshot
    archive_attempts: int
    checksum_attempts: int
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if (
            not _is_exact_request(self.request)
            or type(self.snapshot) is not SourceSnapshot
            or type(self.archive_attempts) is not int
            or not 1 <= self.archive_attempts <= _MAX_ATTEMPTS
            or type(self.checksum_attempts) is not int
            or not 1 <= self.checksum_attempts <= _MAX_ATTEMPTS
        ):
            raise ValueError("capture result must bind the exact request and snapshot")
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("G12L qualification flags must remain false")

    @property
    def capture_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_archive_capture_result",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request.to_canonical_dict(),
            "snapshot": self.snapshot.to_canonical_dict(),
            "archive_attempts": self.archive_attempts,
            "checksum_attempts": self.checksum_attempts,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmArchiveCaptureOutcome:
    result: BinanceUsdmArchiveCaptureResult | None = None
    failure: BinanceUsdmArchiveFailure | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")


def _fetch(
    url: str, fetch: FetchBytes
) -> tuple[bytes | None, int, BinanceUsdmArchiveFailure | None]:
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            response = fetch(url)
        except Exception:
            response = None
        if response is None:
            if attempt == _MAX_ATTEMPTS:
                return None, attempt, BinanceUsdmArchiveFailure(
                    BinanceUsdmArchiveFailureCode.PROVIDER_UNAVAILABLE, url
                )
            continue
        if (
            type(response) is not tuple
            or len(response) != 2
            or type(response[0]) is not int
            or type(response[1]) is not bytes
        ):
            return None, attempt, BinanceUsdmArchiveFailure(
                BinanceUsdmArchiveFailureCode.CONFIGURATION_INVALID, url
            )
        status, body = response
        if status == 200:
            return body, attempt, None
        if status in (401, 403):
            return None, attempt, BinanceUsdmArchiveFailure(
                BinanceUsdmArchiveFailureCode.AUTHENTICATION_REJECTED, url
            )
        if status == 429:
            if attempt < _MAX_ATTEMPTS:
                continue
            return None, attempt, BinanceUsdmArchiveFailure(
                BinanceUsdmArchiveFailureCode.RATE_LIMIT_EXHAUSTED, url
            )
        if 500 <= status <= 599:
            if attempt < _MAX_ATTEMPTS:
                continue
            return None, attempt, BinanceUsdmArchiveFailure(
                BinanceUsdmArchiveFailureCode.PROVIDER_UNAVAILABLE, url
            )
        code = (
            BinanceUsdmArchiveFailureCode.DATA_GAP_DETECTED
            if status == 404
            else BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH
        )
        return None, attempt, BinanceUsdmArchiveFailure(code, url)
    raise AssertionError("unreachable")


def capture_binance_usdm_funding_rate_archive(
    request: BinanceUsdmFundingRateArchiveRequest,
    fetch: FetchBytes,
) -> BinanceUsdmArchiveCaptureOutcome:
    if not _is_exact_request(request) or not callable(fetch):
        return BinanceUsdmArchiveCaptureOutcome(
            failure=BinanceUsdmArchiveFailure(
                BinanceUsdmArchiveFailureCode.CONFIGURATION_INVALID
            )
        )

    archive, archive_attempts, archive_failure = _fetch(_ARCHIVE_URL, fetch)
    checksum, checksum_attempts, checksum_failure = _fetch(_CHECKSUM_URL, fetch)
    if archive is not None and _sha256(archive) != _ARCHIVE_HASH:
        archive_failure = BinanceUsdmArchiveFailure(
            BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH, _ARCHIVE_URL
        )
    if checksum is not None and (
        _sha256(checksum) != _CHECKSUM_HASH
        or checksum != f"{_ARCHIVE_HASH[7:]}  {_ARCHIVE_NAME}\n".encode()
    ):
        checksum_failure = BinanceUsdmArchiveFailure(
            BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH, _CHECKSUM_URL
        )
    failures = [failure for failure in (archive_failure, checksum_failure) if failure]
    if failures:
        precedence = tuple(BinanceUsdmArchiveFailureCode)
        return BinanceUsdmArchiveCaptureOutcome(
            failure=min(failures, key=lambda failure: precedence.index(failure.code))
        )
    if archive is None or checksum is None:
        return BinanceUsdmArchiveCaptureOutcome(
            failure=BinanceUsdmArchiveFailure(
                BinanceUsdmArchiveFailureCode.CONFIGURATION_INVALID
            )
        )
    archive_hash = _sha256(archive)

    snapshot = freeze_source_snapshot(
        members=(
            RawSourceMember(
                "archive/" + _ARCHIVE_NAME,
                archive,
                "0644",
                request.acquired_at_epoch_nanoseconds,
                archive_hash,
            ),
            RawSourceMember(
                "archive/" + _CHECKSUM_NAME,
                checksum,
                "0644",
                request.acquired_at_epoch_nanoseconds,
                _sha256(checksum),
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="binance.public_data",
            source_key=_SOURCE_KEY,
            license_ref="binance.public_data.terms",
            retention_policy_ref="backtest.fixture.retention",
        ),
    ).snapshot
    if snapshot is None:
        return BinanceUsdmArchiveCaptureOutcome(
            failure=BinanceUsdmArchiveFailure(
                BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH
            )
        )
    return BinanceUsdmArchiveCaptureOutcome(
        result=BinanceUsdmArchiveCaptureResult(
            request,
            snapshot,
            archive_attempts,
            checksum_attempts,
        )
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmFundingRateTrace:
    row_number: int
    source_record_hash: str
    snapshot_id: str
    provenance_hash: str
    source_key: str
    archive_member_key: str
    archive_member_hash: str
    checksum_member_key: str
    checksum_member_hash: str
    event_id: str
    event_hash: str

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_funding_rate_trace",
            "schema_version": _SCHEMA_VERSION,
            "row_number": self.row_number,
            "funding_purpose": "funding",
            "source_record_hash": self.source_record_hash,
            "snapshot_id": self.snapshot_id,
            "provenance_hash": self.provenance_hash,
            "source_key": self.source_key,
            "archive_member_key": self.archive_member_key,
            "archive_member_hash": self.archive_member_hash,
            "checksum_member_key": self.checksum_member_key,
            "checksum_member_hash": self.checksum_member_hash,
            "event_id": self.event_id,
            "event_hash": self.event_hash,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmFundingRateNormalizationResult:
    capture: BinanceUsdmArchiveCaptureResult
    events: tuple[MarketEvent, ...]
    traces: tuple[BinanceUsdmFundingRateTrace, ...]
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if len(self.events) != _ROW_COUNT or len(self.traces) != len(self.events):
            raise ValueError("events and traces must exact-cover funding slots")
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("G12L qualification flags must remain false")

    @property
    def normalization_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_funding_rate_normalization_result",
            "schema_version": _SCHEMA_VERSION,
            "capture_hash": self.capture.capture_hash,
            "events": [event.to_canonical_dict() for event in self.events],
            "traces": [trace.to_canonical_dict() for trace in self.traces],
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmFundingRateNormalizationOutcome:
    result: BinanceUsdmFundingRateNormalizationResult | None = None
    failure: BinanceUsdmArchiveFailure | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")


def _funding_rate(value: str) -> tuple[str, int]:
    match = _RATE.fullmatch(value)
    if match is None:
        raise ValueError
    sign, whole, fraction, exponent = match.groups()
    digits = whole + (fraction or "")
    try:
        power = int(exponent or "0") - len(fraction or "") + _RATE_SCALE
        units = int(digits) * 10**power if power >= 0 else 0
    except ValueError as error:
        raise ValueError from error
    if power < 0:
        raise ValueError
    if sign == "-":
        units = -units
    absolute = abs(units)
    normalized = f"{absolute // 10**_RATE_SCALE}.{absolute % 10**_RATE_SCALE:08d}"
    return (("-" if units < 0 else "") + normalized, units)


def _content_failure(
    code: BinanceUsdmArchiveFailureCode,
    subject: str,
    row_number: int | None = None,
) -> BinanceUsdmFundingRateNormalizationOutcome:
    return BinanceUsdmFundingRateNormalizationOutcome(
        failure=BinanceUsdmArchiveFailure(code, subject, row_number)
    )


def normalize_binance_usdm_funding_rate_archive(
    capture: BinanceUsdmArchiveCaptureResult,
) -> BinanceUsdmFundingRateNormalizationOutcome:
    if (
        type(capture) is not BinanceUsdmArchiveCaptureResult
        or not _is_exact_request(capture.request)
        or verify_source_snapshot(capture.snapshot).snapshot is None
    ):
        return _content_failure(
            BinanceUsdmArchiveFailureCode.CONFIGURATION_INVALID, "capture"
        )
    archive_key = "archive/" + _ARCHIVE_NAME
    checksum_key = "archive/" + _CHECKSUM_NAME
    if (
        tuple(member.member_key for member in capture.snapshot.members)
        != (archive_key, checksum_key)
        or capture.snapshot.snapshot_id != _SNAPSHOT_ID
        or capture.snapshot.content_tree_hash != _CONTENT_TREE_HASH
        or capture.snapshot.provenance_hash != _PROVENANCE_HASH
        or capture.snapshot.provenance
        != SourceSnapshotProvenance(
            vendor_key="binance.public_data",
            source_key=_SOURCE_KEY,
            license_ref="binance.public_data.terms",
            retention_policy_ref="backtest.fixture.retention",
        )
    ):
        return _content_failure(
            BinanceUsdmArchiveFailureCode.CONFIGURATION_INVALID, "snapshot_authority"
        )
    archive_member, checksum_member = capture.snapshot.members
    if (
        archive_member.content_hash != _ARCHIVE_HASH
        or checksum_member.content_hash != _CHECKSUM_HASH
        or archive_member.acquired_at_epoch_nanoseconds != _ACQUIRED_AT
        or checksum_member.acquired_at_epoch_nanoseconds != _ACQUIRED_AT
        or archive_member.mode != "0644"
        or checksum_member.mode != "0644"
        or archive_member.declared_sha256 != _ARCHIVE_HASH
        or checksum_member.declared_sha256 != _CHECKSUM_HASH
    ):
        return _content_failure(
            BinanceUsdmArchiveFailureCode.CONFIGURATION_INVALID, "snapshot_identity"
        )
    try:
        archive = capture.snapshot.member_bytes(archive_key)
        checksum = capture.snapshot.member_bytes(checksum_key)
        if (
            _sha256(archive) != _ARCHIVE_HASH
            or _sha256(checksum) != _CHECKSUM_HASH
            or checksum != f"{_ARCHIVE_HASH[7:]}  {_ARCHIVE_NAME}\n".encode()
        ):
            return _content_failure(
                BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH, "checksum"
            )
        with ZipFile(io.BytesIO(archive)) as zip_file:
            if zip_file.namelist() != [_CSV_NAME]:
                return _content_failure(
                    BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH,
                    "zip_layout",
                )
            csv_bytes = zip_file.read(_CSV_NAME)
    except (BadZipFile, KeyError, NotImplementedError, OSError, RuntimeError, ValueError):
        return _content_failure(
            BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH, "zip"
        )
    if b"\r" in csv_bytes or not csv_bytes.endswith(b"\n"):
        return _content_failure(
            BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH, "csv_encoding"
        )
    try:
        rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8"), newline="")))
    except (UnicodeDecodeError, csv.Error):
        return _content_failure(
            BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH, "csv"
        )
    if not rows or tuple(rows[0]) != _CSV_HEADER:
        return _content_failure(
            BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH, "csv_header"
        )
    data_rows = rows[1:]
    faults: list[BinanceUsdmArchiveFailure] = []
    if len(data_rows) != _ROW_COUNT:
        faults.append(
            BinanceUsdmArchiveFailure(
                BinanceUsdmArchiveFailureCode.DATA_GAP_DETECTED, "row_count"
            )
        )

    parsed: list[tuple[int, int, int, str, int, list[str]]] = []
    for row_number, row in enumerate(data_rows, 1):
        if len(row) != len(_CSV_HEADER):
            faults.append(
                BinanceUsdmArchiveFailure(
                    BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH,
                    "csv_columns",
                    row_number,
                )
            )
            continue
        try:
            calc_time = int(row[0])
            funding_interval_hours = int(row[1])
            normalized_rate, rate_units = _funding_rate(row[2])
        except (TypeError, ValueError):
            faults.append(
                BinanceUsdmArchiveFailure(
                    BinanceUsdmArchiveFailureCode.NORMALIZATION_FAILED,
                    "row_value",
                    row_number,
                )
            )
            continue
        nominal_slot = _FIRST_NOMINAL_SLOT_MILLISECONDS + (
            row_number - 1
        ) * _SLOT_MILLISECONDS
        slot_jitter = calc_time - nominal_slot
        if funding_interval_hours != 8:
            faults.append(
                BinanceUsdmArchiveFailure(
                    BinanceUsdmArchiveFailureCode.NORMALIZATION_FAILED,
                    "funding_interval",
                    row_number,
                )
            )
        if slot_jitter not in (0, 1, 2):
            faults.append(
                BinanceUsdmArchiveFailure(
                    BinanceUsdmArchiveFailureCode.DATA_GAP_DETECTED,
                    "funding_slot_sequence",
                    row_number,
                )
            )
        parsed.append(
            (
                calc_time,
                nominal_slot,
                slot_jitter,
                normalized_rate,
                rate_units,
                row,
            )
        )
    if faults:
        precedence = tuple(BinanceUsdmArchiveFailureCode)
        return BinanceUsdmFundingRateNormalizationOutcome(
            failure=min(
                faults,
                key=lambda failure: (
                    precedence.index(failure.code),
                    failure.row_number or 0,
                ),
            )
        )

    events: list[MarketEvent] = []
    traces: list[BinanceUsdmFundingRateTrace] = []
    available_time = UtcInstant(archive_member.acquired_at_epoch_nanoseconds)
    for row_number, parsed_row in enumerate(parsed, 1):
        calc_time, nominal_slot, slot_jitter, normalized_rate, rate_units, row = (
            parsed_row
        )
        source_record_hash = canonical_sha256(tuple(row))
        identity = {
            "type": "binance_usdm_funding_rate_publication_identity",
            "schema_version": _SCHEMA_VERSION,
            "snapshot_id": capture.snapshot.snapshot_id,
            "calc_time_milliseconds": calc_time,
        }
        try:
            event = MarketEvent(
                event_id="binance-usdm-funding-rate-v1:" + canonical_sha256(identity),
                stream_key="binance_usdm.funding_rate.publications.btcusdt.v1",
                event_type="binance_usdm_funding_rate_publication.v1",
                capability=_FUNDING_CAPABILITY,
                instrument_id=capture.request.instrument_id,
                event_time=UtcInstant(calc_time * 1_000_000),
                available_time=available_time,
                phase=_PHASE,
                source_sequence=SourceSequence(row_number - 1),
                revision_id=archive_member.content_hash,
                supersedes_revision_id=None,
                source_key=_SOURCE_KEY,
                source_hash=archive_member.content_hash,
                payload={
                    "funding_purpose": "funding",
                    "calc_time_milliseconds": calc_time,
                    "nominal_slot_time_milliseconds": nominal_slot,
                    "slot_jitter_milliseconds": slot_jitter,
                    "funding_interval_hours": 8,
                    "raw_funding_rate": row[2],
                    "funding_rate": normalized_rate,
                    "funding_rate_units": rate_units,
                    "funding_rate_scale": _RATE_SCALE,
                    "source_record_hash": source_record_hash,
                },
            )
        except (TypeError, ValueError):
            return _content_failure(
                BinanceUsdmArchiveFailureCode.NORMALIZATION_FAILED,
                "market_event",
                row_number,
            )
        events.append(event)
        traces.append(
            BinanceUsdmFundingRateTrace(
                row_number,
                source_record_hash,
                capture.snapshot.snapshot_id,
                capture.snapshot.provenance_hash,
                capture.snapshot.provenance.source_key,
                archive_key,
                archive_member.content_hash,
                checksum_key,
                checksum_member.content_hash,
                event.event_id,
                event.event_hash,
            )
        )
    return BinanceUsdmFundingRateNormalizationOutcome(
        result=BinanceUsdmFundingRateNormalizationResult(
            capture, tuple(events), tuple(traces)
        )
    )
