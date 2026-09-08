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
_ARCHIVE_NAME = "BTCUSDT-1m-2024-01-01.zip"
_CHECKSUM_NAME = _ARCHIVE_NAME + ".CHECKSUM"
_BASE_URL = (
    "https://data.binance.vision/data/futures/um/daily/markPriceKlines/"
    "BTCUSDT/1m/"
)
_ARCHIVE_URL = _BASE_URL + _ARCHIVE_NAME
_CHECKSUM_URL = _BASE_URL + _CHECKSUM_NAME
_SOURCE_KEY = (
    "binance.public_data.futures.um.daily.mark_price_klines."
    "btcusdt.1m.2024-01-01"
)
_MAX_ATTEMPTS = 3
_ACQUIRED_AT = 1_786_920_753_047_737_420
_ARCHIVE_HASH = "sha256:660efeefdc875f052051b94c2976babd013f64c6633bf58ba030764771747b90"
_CHECKSUM_HASH = "sha256:ea5548dadd83fad69bbc9db3a24560b7d3f988e54299d2c6aa87e85351e05215"
_SNAPSHOT_ID = "sha256:df0869271a08320107381a60e9be9012d9645e076ef349c551d34aa332d2be80"
_CONTENT_TREE_HASH = "sha256:9b12fcf35779d78b2d0293692deb595d54b4506bbb9da6dde44e525a8c968b32"
_PROVENANCE_HASH = "sha256:4dba4a7b2140ac82bc7c736f856b1fa8ea0d2ff58e8e5f7c659f4cb870aed2ca"
_CSV_NAME = "BTCUSDT-1m-2024-01-01.csv"
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
_FIRST_OPEN_MILLISECONDS = 1_704_067_200_000
_ROW_COUNT = 1440
_PRICE = re.compile(r"[0-9]+(?:\.[0-9]{1,8})?\Z")
_PHASE = TimelinePhase(0, "market_data")
_POINT_CAPABILITY = MarketBundleCapability("price.point", 1)
_BAR_CAPABILITY = MarketBundleCapability("price.bar", 1)

FetchBytes = Callable[[str], tuple[int, bytes]]


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


@dataclass(frozen=True, slots=True)
class BinanceUsdmMarkPriceArchiveRequest:
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
            "type": "binance_usdm_mark_price_archive_request",
            "schema_version": _SCHEMA_VERSION,
            "instrument_id": self.instrument_id.to_canonical_dict(),
            "symbol": "BTCUSDT",
            "interval": "1m",
            "utc_date": "2024-01-01",
            "archive_url": _ARCHIVE_URL,
            "checksum_url": _CHECKSUM_URL,
            "acquired_at_epoch_nanoseconds": self.acquired_at_epoch_nanoseconds,
        }


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
    request: BinanceUsdmMarkPriceArchiveRequest
    snapshot: SourceSnapshot
    archive_attempts: int
    checksum_attempts: int
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
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


def capture_binance_usdm_mark_price_archive(
    request: BinanceUsdmMarkPriceArchiveRequest,
    fetch: FetchBytes,
) -> BinanceUsdmArchiveCaptureOutcome:
    if type(request) is not BinanceUsdmMarkPriceArchiveRequest or not callable(fetch):
        return BinanceUsdmArchiveCaptureOutcome(
            failure=BinanceUsdmArchiveFailure(
                BinanceUsdmArchiveFailureCode.CONFIGURATION_INVALID
            )
        )

    archive, archive_attempts, archive_failure = _fetch(_ARCHIVE_URL, fetch)
    checksum, checksum_attempts, checksum_failure = _fetch(_CHECKSUM_URL, fetch)
    failures = [
        failure
        for failure in (archive_failure, checksum_failure)
        if failure is not None
    ]
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
    expected = f"{archive_hash[7:]}  {_ARCHIVE_NAME}\n".encode()
    if (
        checksum != expected
        or archive_hash != _ARCHIVE_HASH
        or _sha256(checksum) != _CHECKSUM_HASH
    ):
        return BinanceUsdmArchiveCaptureOutcome(
            failure=BinanceUsdmArchiveFailure(
                BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH,
                _CHECKSUM_URL,
            )
        )

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
class BinanceUsdmMarkPriceTrace:
    row_number: int
    price_purpose: str
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
            "type": "binance_usdm_mark_price_trace",
            "schema_version": _SCHEMA_VERSION,
            "row_number": self.row_number,
            "price_purpose": self.price_purpose,
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
class BinanceUsdmMarkPriceNormalizationResult:
    capture: BinanceUsdmArchiveCaptureResult
    events: tuple[MarketEvent, ...]
    traces: tuple[BinanceUsdmMarkPriceTrace, ...]
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if len(self.events) != _ROW_COUNT * 3 or len(self.traces) != len(self.events):
            raise ValueError("events and traces must exact-cover three purpose streams")
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("G12L qualification flags must remain false")

    @property
    def normalization_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_mark_price_normalization_result",
            "schema_version": _SCHEMA_VERSION,
            "capture_hash": self.capture.capture_hash,
            "events": [event.to_canonical_dict() for event in self.events],
            "traces": [trace.to_canonical_dict() for trace in self.traces],
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmMarkPriceNormalizationOutcome:
    result: BinanceUsdmMarkPriceNormalizationResult | None = None
    failure: BinanceUsdmArchiveFailure | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")


def _price_units(value: str) -> int:
    if _PRICE.fullmatch(value) is None:
        raise ValueError
    whole, _, fraction = value.partition(".")
    try:
        units = int(whole) * 100_000_000 + int(fraction.ljust(8, "0"))
    except ValueError as error:
        raise ValueError from error
    if units <= 0:
        raise ValueError
    return units


def _content_failure(
    code: BinanceUsdmArchiveFailureCode,
    subject: str,
    row_number: int | None = None,
) -> BinanceUsdmMarkPriceNormalizationOutcome:
    return BinanceUsdmMarkPriceNormalizationOutcome(
        failure=BinanceUsdmArchiveFailure(code, subject, row_number)
    )


def normalize_binance_usdm_mark_price_archive(
    capture: BinanceUsdmArchiveCaptureResult,
) -> BinanceUsdmMarkPriceNormalizationOutcome:
    if (
        type(capture) is not BinanceUsdmArchiveCaptureResult
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
    if any(len(row) != len(_CSV_HEADER) for row in rows[1:]):
        return _content_failure(
            BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH, "csv_columns"
        )

    faults: list[BinanceUsdmArchiveFailure] = []
    if len(rows[1:]) != _ROW_COUNT:
        faults.append(
            BinanceUsdmArchiveFailure(
                BinanceUsdmArchiveFailureCode.DATA_GAP_DETECTED, "row_count"
            )
        )
    parsed: list[tuple[int, int, tuple[int, int, int, int], list[str]]] = []
    for row_number, row in enumerate(rows[1:], 1):
        try:
            open_time = int(row[0])
            close_time = int(row[6])
            prices = tuple(_price_units(value) for value in row[1:5])
            count = int(row[8])
        except ValueError:
            faults.append(
                BinanceUsdmArchiveFailure(
                    BinanceUsdmArchiveFailureCode.NORMALIZATION_FAILED,
                    "row_value",
                    row_number,
                )
            )
            continue
        expected_open = _FIRST_OPEN_MILLISECONDS + (row_number - 1) * 60_000
        if open_time != expected_open:
            faults.append(
                BinanceUsdmArchiveFailure(
                    BinanceUsdmArchiveFailureCode.DATA_GAP_DETECTED,
                    "minute_sequence",
                    row_number,
                )
            )
        if close_time != open_time + 59_999:
            faults.append(
                BinanceUsdmArchiveFailure(
                    BinanceUsdmArchiveFailureCode.NORMALIZATION_FAILED,
                    "closed_row",
                    row_number,
                )
            )
        open_units, high_units, low_units, close_units = prices
        if (
            count < 0
            or not low_units <= open_units <= high_units
            or not low_units <= close_units <= high_units
        ):
            faults.append(
                BinanceUsdmArchiveFailure(
                    BinanceUsdmArchiveFailureCode.NORMALIZATION_FAILED,
                    "ohlc",
                    row_number,
                )
            )
        parsed.append((open_time, close_time, prices, row))
    if faults:
        precedence = tuple(BinanceUsdmArchiveFailureCode)
        return BinanceUsdmMarkPriceNormalizationOutcome(
            failure=min(
                faults,
                key=lambda failure: (
                    precedence.index(failure.code),
                    failure.row_number or 0,
                ),
            )
        )

    events: list[MarketEvent] = []
    traces: list[BinanceUsdmMarkPriceTrace] = []
    available_time = UtcInstant(archive_member.acquired_at_epoch_nanoseconds)
    for row_number, (open_time, close_time, prices, row) in enumerate(parsed, 1):
        open_units, high_units, low_units, close_units = prices
        source_record_hash = canonical_sha256(tuple(row))
        definitions = (
            (
                "valuation",
                "binance_usdm.mark_price.valuation.btcusdt.1m.v1",
                "binance_usdm_mark_price_point.v1",
                _POINT_CAPABILITY,
                {"price_units": close_units, "price_scale": 8},
            ),
            (
                "margin",
                "binance_usdm.mark_price.margin.btcusdt.1m.v1",
                "binance_usdm_mark_price_point.v1",
                _POINT_CAPABILITY,
                {"price_units": close_units, "price_scale": 8},
            ),
            (
                "liquidation",
                "binance_usdm.mark_price.liquidation.btcusdt.1m.v1",
                "binance_usdm_mark_price_bar.v1",
                _BAR_CAPABILITY,
                {
                    "open_units": open_units,
                    "high_units": high_units,
                    "low_units": low_units,
                    "close_units": close_units,
                    "price_scale": 8,
                },
            ),
        )
        for purpose, stream_key, event_type, capability, values in definitions:
            identity = {
                "type": "binance_usdm_mark_price_event_identity",
                "schema_version": _SCHEMA_VERSION,
                "snapshot_id": capture.snapshot.snapshot_id,
                "row_number": row_number,
                "price_purpose": purpose,
            }
            event_id = "binance-usdm-mark-price-v1:" + canonical_sha256(identity)
            try:
                event = MarketEvent(
                    event_id=event_id,
                    stream_key=stream_key,
                    event_type=event_type,
                    capability=capability,
                    instrument_id=capture.request.instrument_id,
                    event_time=UtcInstant(close_time * 1_000_000),
                    available_time=available_time,
                    phase=_PHASE,
                    source_sequence=SourceSequence(row_number - 1),
                    revision_id=archive_member.content_hash,
                    supersedes_revision_id=None,
                    source_key=_SOURCE_KEY,
                    source_hash=archive_member.content_hash,
                    payload={
                        "price_purpose": purpose,
                        "open_time_milliseconds": open_time,
                        "close_time_milliseconds": close_time,
                        "source_record_hash": source_record_hash,
                        **values,
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
                BinanceUsdmMarkPriceTrace(
                    row_number,
                    purpose,
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
    return BinanceUsdmMarkPriceNormalizationOutcome(
        result=BinanceUsdmMarkPriceNormalizationResult(
            capture,
            tuple(events),
            tuple(traces),
        )
    )
