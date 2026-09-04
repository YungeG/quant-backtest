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
_ARCHIVE_NAME = "BTCUSDT-aggTrades-2020-01-01.zip"
_CHECKSUM_NAME = _ARCHIVE_NAME + ".CHECKSUM"
_BASE_URL = "https://data.binance.vision/data/futures/um/daily/aggTrades/BTCUSDT/"
_ARCHIVE_URL = _BASE_URL + _ARCHIVE_NAME
_CHECKSUM_URL = _BASE_URL + _CHECKSUM_NAME
_SOURCE_KEY = "binance.public_data.futures.um.daily.aggtrades.btcusdt.2020-01-01"
_MAX_ATTEMPTS = 3
_ACQUIRED_AT = 1_786_925_819_571_748_917
_ARCHIVE_HASH = "sha256:638e72c179e4965c2a6521bb27295930d09126433efe0cc3acd4e925ada955ac"
_CHECKSUM_HASH = "sha256:54f9a3ec8d0ea0363fcd730c2eb43399fa425d2d1fd803a7261f761af78d8499"
_SNAPSHOT_ID = "sha256:84e362ddf3a1a7567c436160bb4bb6102324cd20474a4c2c2b0a38b388142c65"
_CONTENT_TREE_HASH = "sha256:3e51e591737b5928ce796dc555b266b7d49d48e88b1051fbb9c6aa0b957993d7"
_PROVENANCE_HASH = "sha256:70908485e1e1baddf684248282fce1ba78dd5df4f066ccc3cf714ec892bac5d7"
_REQUEST_HASH = "sha256:71444a4b733b10f5b94508c74c5a941afc3c4ea531f1971bb71fcc0acdc64f91"
_CSV_NAME = "BTCUSDT-aggTrades-2020-01-01.csv"
_ROW_COUNT = 71_359
_FIRST_AGGREGATE_TRADE_ID = 18_374_167
_DAY_START_MILLISECONDS = 1_577_836_800_000
_DAY_END_MILLISECONDS = 1_577_923_200_000
_PRICE = re.compile(r"[0-9]+\.[0-9]{1,2}\Z")
_QUANTITY = re.compile(r"[0-9]+\.[0-9]{1,3}\Z")
_PHASE = TimelinePhase(0, "market_data")
_POINT_CAPABILITY = MarketBundleCapability("price.point", 1)

FetchBytes = Callable[[str], tuple[int, bytes]]


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


@dataclass(frozen=True, slots=True)
class BinanceUsdmAggregateTradesArchiveRequest:
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
            "type": "binance_usdm_aggregate_trades_archive_request",
            "schema_version": _SCHEMA_VERSION,
            "instrument_id": self.instrument_id.to_canonical_dict(),
            "symbol": "BTCUSDT",
            "utc_date": "2020-01-01",
            "archive_url": _ARCHIVE_URL,
            "checksum_url": _CHECKSUM_URL,
            "acquired_at_epoch_nanoseconds": self.acquired_at_epoch_nanoseconds,
        }


def _is_exact_request(value: object) -> bool:
    try:
        return (
            type(value) is BinanceUsdmAggregateTradesArchiveRequest
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
    request: BinanceUsdmAggregateTradesArchiveRequest
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


def capture_binance_usdm_aggregate_trades_archive(
    request: BinanceUsdmAggregateTradesArchiveRequest,
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
class BinanceUsdmAggregateTradesTrace:
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
            "type": "binance_usdm_aggregate_trades_trace",
            "schema_version": _SCHEMA_VERSION,
            "row_number": self.row_number,
            "price_purpose": "execution_reference",
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
class BinanceUsdmAggregateTradesNormalizationResult:
    capture: BinanceUsdmArchiveCaptureResult
    events: tuple[MarketEvent, ...]
    traces: tuple[BinanceUsdmAggregateTradesTrace, ...]
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        if len(self.events) != _ROW_COUNT or len(self.traces) != len(self.events):
            raise ValueError("events and traces must exact-cover aggregate trades")
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("G12L qualification flags must remain false")

    @property
    def normalization_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_aggregate_trades_normalization_result",
            "schema_version": _SCHEMA_VERSION,
            "capture_hash": self.capture.capture_hash,
            "events": [event.to_canonical_dict() for event in self.events],
            "traces": [trace.to_canonical_dict() for trace in self.traces],
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


@dataclass(frozen=True, slots=True)
class BinanceUsdmAggregateTradesNormalizationOutcome:
    result: BinanceUsdmAggregateTradesNormalizationResult | None = None
    failure: BinanceUsdmArchiveFailure | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")


def _decimal_units(value: str, *, scale: int, pattern: re.Pattern[str]) -> int:
    if pattern.fullmatch(value) is None:
        raise ValueError
    whole, _, fraction = value.partition(".")
    try:
        units = int(whole) * 10**scale + int(fraction.ljust(scale, "0"))
    except ValueError as error:
        raise ValueError from error
    if units <= 0:
        raise ValueError
    return units


def _content_failure(
    code: BinanceUsdmArchiveFailureCode,
    subject: str,
    row_number: int | None = None,
) -> BinanceUsdmAggregateTradesNormalizationOutcome:
    return BinanceUsdmAggregateTradesNormalizationOutcome(
        failure=BinanceUsdmArchiveFailure(code, subject, row_number)
    )


def normalize_binance_usdm_aggregate_trades_archive(
    capture: BinanceUsdmArchiveCaptureResult,
) -> BinanceUsdmAggregateTradesNormalizationOutcome:
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
    faults: list[BinanceUsdmArchiveFailure] = []
    if len(rows) != _ROW_COUNT:
        faults.append(
            BinanceUsdmArchiveFailure(
                BinanceUsdmArchiveFailureCode.DATA_GAP_DETECTED, "row_count"
            )
        )

    parsed: list[tuple[int, int, int, int, int, int, bool, list[str]]] = []
    previous_time = _DAY_START_MILLISECONDS
    for row_number, row in enumerate(rows, 1):
        if len(row) != 7:
            faults.append(
                BinanceUsdmArchiveFailure(
                    BinanceUsdmArchiveFailureCode.SOURCE_SCHEMA_MISMATCH,
                    "csv_columns",
                    row_number,
                )
            )
            continue
        try:
            aggregate_trade_id = int(row[0])
            price_units = _decimal_units(row[1], scale=2, pattern=_PRICE)
            quantity_units = _decimal_units(row[2], scale=3, pattern=_QUANTITY)
            first_trade_id = int(row[3])
            last_trade_id = int(row[4])
            transaction_time = int(row[5])
            if row[6] not in ("true", "false"):
                raise ValueError
            is_buyer_maker = row[6] == "true"
        except (TypeError, ValueError):
            faults.append(
                BinanceUsdmArchiveFailure(
                    BinanceUsdmArchiveFailureCode.NORMALIZATION_FAILED,
                    "row_value",
                    row_number,
                )
            )
            continue
        if aggregate_trade_id != _FIRST_AGGREGATE_TRADE_ID + row_number - 1:
            faults.append(
                BinanceUsdmArchiveFailure(
                    BinanceUsdmArchiveFailureCode.DATA_GAP_DETECTED,
                    "aggregate_trade_sequence",
                    row_number,
                )
            )
        if not (
            _DAY_START_MILLISECONDS <= transaction_time < _DAY_END_MILLISECONDS
            and previous_time <= transaction_time
        ):
            faults.append(
                BinanceUsdmArchiveFailure(
                    BinanceUsdmArchiveFailureCode.DATA_GAP_DETECTED,
                    "transaction_time_sequence",
                    row_number,
                )
            )
        if min(first_trade_id, last_trade_id) < 0 or first_trade_id > last_trade_id:
            faults.append(
                BinanceUsdmArchiveFailure(
                    BinanceUsdmArchiveFailureCode.NORMALIZATION_FAILED,
                    "trade_id_range",
                    row_number,
                )
            )
        previous_time = transaction_time
        parsed.append(
            (
                aggregate_trade_id,
                price_units,
                quantity_units,
                first_trade_id,
                last_trade_id,
                transaction_time,
                is_buyer_maker,
                row,
            )
        )
    if faults:
        precedence = tuple(BinanceUsdmArchiveFailureCode)
        return BinanceUsdmAggregateTradesNormalizationOutcome(
            failure=min(
                faults,
                key=lambda failure: (
                    precedence.index(failure.code),
                    failure.row_number or 0,
                ),
            )
        )

    events: list[MarketEvent] = []
    traces: list[BinanceUsdmAggregateTradesTrace] = []
    available_time = UtcInstant(archive_member.acquired_at_epoch_nanoseconds)
    for row_number, parsed_row in enumerate(parsed, 1):
        (
            aggregate_trade_id,
            price_units,
            quantity_units,
            first_trade_id,
            last_trade_id,
            transaction_time,
            is_buyer_maker,
            row,
        ) = parsed_row
        source_record_hash = canonical_sha256(tuple(row))
        identity = {
            "type": "binance_usdm_aggregate_trade_event_identity",
            "schema_version": _SCHEMA_VERSION,
            "snapshot_id": capture.snapshot.snapshot_id,
            "aggregate_trade_id": aggregate_trade_id,
        }
        try:
            event = MarketEvent(
                event_id="binance-usdm-aggregate-trade-v1:" + canonical_sha256(identity),
                stream_key="binance_usdm.aggregate_trades.execution_reference.btcusdt.v1",
                event_type="binance_usdm_aggregate_trade.v1",
                capability=_POINT_CAPABILITY,
                instrument_id=capture.request.instrument_id,
                event_time=UtcInstant(transaction_time * 1_000_000),
                available_time=available_time,
                phase=_PHASE,
                source_sequence=SourceSequence(row_number - 1),
                revision_id=archive_member.content_hash,
                supersedes_revision_id=None,
                source_key=_SOURCE_KEY,
                source_hash=archive_member.content_hash,
                payload={
                    "price_purpose": "execution_reference",
                    "aggregate_trade_id": aggregate_trade_id,
                    "price": row[1],
                    "price_units": price_units,
                    "price_scale": 2,
                    "quantity": row[2],
                    "quantity_units": quantity_units,
                    "quantity_scale": 3,
                    "first_trade_id": first_trade_id,
                    "last_trade_id": last_trade_id,
                    "transaction_time_milliseconds": transaction_time,
                    "is_buyer_maker": is_buyer_maker,
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
            BinanceUsdmAggregateTradesTrace(
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
    return BinanceUsdmAggregateTradesNormalizationOutcome(
        result=BinanceUsdmAggregateTradesNormalizationResult(
            capture, tuple(events), tuple(traces)
        )
    )
