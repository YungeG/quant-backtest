"""Bounded KORU funding-history capture and exact publication projection."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation, localcontext
from email.utils import parsedate_to_datetime
from enum import Enum
from typing import cast

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
_INSTRUMENT = InstrumentId(VenueId("binance_usdm"), "koru-usdt-tradifi-perpetual")
_BASE_URL = "https://fapi.binance.com/fapi/v1/fundingRate"
_POST_ADJUSTMENT_START_MILLISECONDS = 1_784_109_600_000
_MAX_ATTEMPTS = 3
_SCALE = 8
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_RATE = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,8})?\Z")
_MARK = re.compile(r"(?:0|[1-9][0-9]*)(?:\.[0-9]{1,8})?\Z")
_RESPONSE_MEMBER_KEY = "response/funding-history.json"
_RECEIPT_MEMBER_KEY = "acquisition/acquisition-receipt.json"
_ECONOMIC_POLICY_REF = "binance.fapi.funding-rate-effective-at-funding-time.v1"
_STREAM_KEY = "binance_usdm.funding_history.publications.koruusdt.v1"
_EVENT_TYPE = "binance_usdm_koru_funding_history_publication_v1"
_CAPABILITY = MarketBundleCapability("binance_usdm.funding-publications", 1)
_PHASE = TimelinePhase(110, "funding_settlement")
_PREFIX_CLASSIFICATION = "unknown_unproven"
_SUFFIX_CLASSIFICATION = "unknown_unproven"
_COMPLETENESS_CLASSIFICATION = "provider_completeness_unknown"
_RESPONSE_FIELDS_WITHOUT_TYPE = ("symbol", "fundingTime", "fundingRate", "markPrice")
_RESPONSE_FIELDS_WITH_TYPE = (*_RESPONSE_FIELDS_WITHOUT_TYPE, "rateType")
_EVENT_PAYLOAD_KEYS = frozenset(
    {
        "funding_purpose",
        "funding_slot_milliseconds",
        "funding_rate_units",
        "funding_rate_scale",
        "raw_funding_rate",
        "mark_price_units",
        "mark_price_scale",
        "raw_mark_price",
        "rate_type",
        "source_record_hash",
        "request_hash",
        "capture_hash",
        "source_snapshot_id",
        "source_snapshot_hash",
        "source_provenance_hash",
        "response_member_key",
        "response_member_hash",
        "receipt_member_key",
        "receipt_member_hash",
        "receipt_hash",
        "economic_policy_ref",
        "observed_at_epoch_nanoseconds",
        "acquired_at_epoch_nanoseconds",
    }
)

_SourceRow = tuple[str, int, str, str, str | None, bool]


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _content_hash(name: str, value: object) -> str:
    if type(value) is not str or _HASH.fullmatch(value) is None:
        raise ValueError(f"{name} must be a canonical sha256 digest")
    return value


def _exact_milliseconds(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be exact nonnegative milliseconds")
    return value


def _exact_nanoseconds(name: str, value: object) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be an exact UTC instant")
    _ = UtcInstant(value)
    return value


def _date_header_nanoseconds(value: object) -> int:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError("date_header must be exact canonical HTTP Date text")
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "date_header must be exact canonical HTTP Date text"
        ) from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("date_header must be UTC")
    parsed = parsed.astimezone(UTC)
    if parsed.strftime("%a, %d %b %Y %H:%M:%S GMT") != value:
        raise ValueError("date_header must be exact canonical HTTP Date text")
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    delta = parsed - epoch
    return (
        delta.days * 86_400_000_000_000
        + delta.seconds * 1_000_000_000
        + delta.microseconds * 1_000
    )


def _captured_at_utc(epoch_nanoseconds: int) -> str:
    seconds, nanoseconds = divmod(epoch_nanoseconds, 1_000_000_000)
    value = datetime.fromtimestamp(seconds, UTC)
    fraction = f"{nanoseconds:09d}".rstrip("0")
    return value.strftime("%Y-%m-%dT%H:%M:%S") + f".{fraction or '000'}Z"


def _request_url(start: int, end: int, limit: int) -> str:
    return f"{_BASE_URL}?symbol={_SYMBOL}&startTime={start}&endTime={end}&limit={limit}"


def _provider_request(start: int, end: int, limit: int) -> dict[str, object]:
    return {
        "end_time_milliseconds": end,
        "limit": limit,
        "start_time_milliseconds": start,
        "symbol": _SYMBOL,
    }


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruFundingRateHistoryTransportResponseV1:
    method: str
    requested_url: str
    final_url: str
    status: int
    body: bytes
    date_header: str
    acquired_at_epoch_nanoseconds: int

    def __post_init__(self) -> None:
        if type(self.method) is not str or not self.method:
            raise ValueError("method must be exact nonempty text")
        if type(self.requested_url) is not str or not self.requested_url:
            raise ValueError("requested_url must be exact nonempty text")
        if type(self.final_url) is not str or not self.final_url:
            raise ValueError("final_url must be exact nonempty text")
        if type(self.status) is not int:
            raise ValueError("status must be an exact integer")
        if type(self.body) is not bytes:
            raise ValueError("body must be exact bytes")
        if type(self.date_header) is not str:
            raise ValueError("date_header must be exact text")
        _ = _exact_nanoseconds(
            "acquired_at_epoch_nanoseconds", self.acquired_at_epoch_nanoseconds
        )


FetchResponse = Callable[[str], BinanceUsdmKoruFundingRateHistoryTransportResponseV1]


def _trusted_transport_response(
    value: object,
) -> BinanceUsdmKoruFundingRateHistoryTransportResponseV1 | None:
    if type(value) is not BinanceUsdmKoruFundingRateHistoryTransportResponseV1:
        return None
    try:
        return BinanceUsdmKoruFundingRateHistoryTransportResponseV1(
            value.method,
            value.requested_url,
            value.final_url,
            value.status,
            value.body,
            value.date_header,
            value.acquired_at_epoch_nanoseconds,
        )
    except (AttributeError, TypeError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruFundingRateHistorySourceBoundedRequestV1:
    instrument_id: InstrumentId
    start_time_milliseconds: int
    end_time_milliseconds: int
    limit: int
    expected_response_sha256: str

    def __post_init__(self) -> None:
        if (
            type(self.instrument_id) is not InstrumentId
            or self.instrument_id != _INSTRUMENT
        ):
            raise ValueError("instrument_id must be the exact KORU tradifi perpetual")
        start = _exact_milliseconds(
            "start_time_milliseconds", self.start_time_milliseconds
        )
        end = _exact_milliseconds("end_time_milliseconds", self.end_time_milliseconds)
        if start < _POST_ADJUSTMENT_START_MILLISECONDS:
            raise ValueError(
                "start_time_milliseconds must be on or after 2026-07-15T10:00Z"
            )
        if end <= start:
            raise ValueError("end_time_milliseconds must be inclusive and after start")
        if type(self.limit) is not int or not 1 <= self.limit <= 1000:
            raise ValueError("limit must be an exact integer from 1 through 1000")
        _ = _content_hash("expected_response_sha256", self.expected_response_sha256)

    @property
    def symbol(self) -> str:
        return _SYMBOL

    @property
    def url(self) -> str:
        return _request_url(
            self.start_time_milliseconds, self.end_time_milliseconds, self.limit
        )

    @property
    def request_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_funding_rate_history_source_bounded_request_v1",
            "schema_version": _SCHEMA_VERSION,
            "instrument_id": self.instrument_id.to_canonical_dict(),
            "symbol": _SYMBOL,
            "start_time_milliseconds": self.start_time_milliseconds,
            "end_time_milliseconds": self.end_time_milliseconds,
            "limit": self.limit,
            "url": self.url,
            "expected_response_sha256": self.expected_response_sha256,
        }


def _trusted_request(
    value: object,
) -> BinanceUsdmKoruFundingRateHistorySourceBoundedRequestV1 | None:
    if type(value) is not BinanceUsdmKoruFundingRateHistorySourceBoundedRequestV1:
        return None
    try:
        rebuilt = BinanceUsdmKoruFundingRateHistorySourceBoundedRequestV1(
            value.instrument_id,
            value.start_time_milliseconds,
            value.end_time_milliseconds,
            value.limit,
            value.expected_response_sha256,
        )
        if rebuilt.to_canonical_dict() != value.to_canonical_dict():
            return None
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt


def _source_key(
    request: BinanceUsdmKoruFundingRateHistorySourceBoundedRequestV1,
    observed_at_epoch_nanoseconds: int,
) -> str:
    return (
        "binance.fapi.funding_rate_history.koruusdt."
        f"{request.start_time_milliseconds}.{request.end_time_milliseconds}."
        f"observed-at-{observed_at_epoch_nanoseconds}"
    )


def _provenance(
    request: BinanceUsdmKoruFundingRateHistorySourceBoundedRequestV1,
    observed_at_epoch_nanoseconds: int,
) -> SourceSnapshotProvenance:
    return SourceSnapshotProvenance(
        vendor_key="binance.fapi",
        source_key=_source_key(request, observed_at_epoch_nanoseconds),
        license_ref="binance.api.terms",
        retention_policy_ref="backtest.fixture.retention",
    )


class BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1(str, Enum):
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
class BinanceUsdmKoruFundingRateHistorySourceBoundedFailureV1:
    code: BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1
    subject: str | None = None
    row_number: int | None = None

    def __post_init__(self) -> None:
        if (
            type(self.code)
            is not BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1
        ):
            raise TypeError("code must be an exact KORU funding-history failure code")
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
            "type": "binance_usdm_koru_funding_rate_history_source_bounded_failure_v1",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "subject": self.subject,
            "row_number": self.row_number,
        }


def _failure(
    code: BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1,
    subject: str | None = None,
    row_number: int | None = None,
) -> BinanceUsdmKoruFundingRateHistorySourceBoundedFailureV1:
    return BinanceUsdmKoruFundingRateHistorySourceBoundedFailureV1(
        code, subject, row_number
    )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _reject_number(_: str) -> object:
    raise ValueError("JSON floating-point numbers are forbidden")


def _provider_json(raw: bytes) -> object:
    try:
        parsed = cast(
            object,
            json.loads(
                raw.decode("utf-8"),
                parse_float=_reject_number,
                parse_constant=_reject_number,
                object_pairs_hook=_unique_object,
            ),
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValueError,
    ) as error:
        raise ValueError("provider JSON is invalid") from error
    compact = json.dumps(
        parsed, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")
    if raw != compact or b"\r" in raw:
        raise ValueError("provider JSON must be exact compact UTF-8")
    return parsed


def _receipt_bytes(
    request: BinanceUsdmKoruFundingRateHistorySourceBoundedRequestV1,
    response: BinanceUsdmKoruFundingRateHistoryTransportResponseV1,
    record_count: int,
) -> bytes:
    receipt = {
        "byte_count": len(response.body),
        "captured_at_utc": _captured_at_utc(response.acquired_at_epoch_nanoseconds),
        "date_header": response.date_header,
        "record_count": record_count,
        "request": _provider_request(
            request.start_time_milliseconds,
            request.end_time_milliseconds,
            request.limit,
        ),
        "response_sha256": _sha256(response.body),
        "schema_version": _SCHEMA_VERSION,
        "status": response.status,
        "type": "binance_usdm_koru_funding_history_provider_capture_receipt_v1",
        "url": response.final_url,
    }
    return (
        json.dumps(
            receipt, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True
        )
        + "\n"
    ).encode("utf-8")


def _receipt_facts(
    request: BinanceUsdmKoruFundingRateHistorySourceBoundedRequestV1,
    receipt: bytes,
    raw: bytes,
) -> tuple[int, int, str]:
    try:
        parsed_receipt = cast(
            object,
            json.loads(
                receipt.decode("utf-8"),
                parse_float=_reject_number,
                parse_constant=_reject_number,
                object_pairs_hook=_unique_object,
            ),
        )
        if type(parsed_receipt) is not dict:
            raise ValueError("receipt must be an object")
        value = cast(dict[str, object], parsed_receipt)
        date_header = value["date_header"]
        captured_at = value["captured_at_utc"]
        status = value["status"]
        if (
            type(date_header) is not str
            or type(captured_at) is not str
            or type(status) is not int
        ):
            raise ValueError("receipt transport primitives are invalid")
        match = re.fullmatch(
            r"([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})\.([0-9]{3,9})Z",
            captured_at,
        )
        if match is None:
            raise ValueError("captured_at_utc is invalid")
        acquired_at = datetime.strptime(match[1], "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=UTC
        )
        epoch = datetime(1970, 1, 1, tzinfo=UTC)
        delta = acquired_at - epoch
        acquired_at_nanoseconds = (
            delta.days * 86_400_000_000_000
            + delta.seconds * 1_000_000_000
            + int(match[2].ljust(9, "0"))
        )
        observed_at_nanoseconds = _date_header_nanoseconds(date_header)
        parsed_raw = _provider_json(raw)
        if type(parsed_raw) is not list:
            raise ValueError("response must be an array")
        parsed_rows = cast(list[object], parsed_raw)
        response = BinanceUsdmKoruFundingRateHistoryTransportResponseV1(
            "GET",
            request.url,
            request.url,
            status,
            raw,
            date_header,
            acquired_at_nanoseconds,
        )
    except (KeyError, TypeError, UnicodeDecodeError, ValueError) as error:
        raise ValueError("receipt transport facts are invalid") from error
    if (
        response.status != 200
        or observed_at_nanoseconds < request.end_time_milliseconds * 1_000_000
        or acquired_at_nanoseconds < observed_at_nanoseconds
        or receipt != _receipt_bytes(request, response, len(parsed_rows))
    ):
        raise ValueError("receipt transport facts are invalid")
    return observed_at_nanoseconds, acquired_at_nanoseconds, date_header


def _snapshot_matches_request(
    request: BinanceUsdmKoruFundingRateHistorySourceBoundedRequestV1,
    snapshot: SourceSnapshot,
) -> bool:
    if (
        type(snapshot) is not SourceSnapshot
        or verify_source_snapshot(snapshot).snapshot is None
        or tuple(member.member_key for member in snapshot.members)
        != (_RECEIPT_MEMBER_KEY, _RESPONSE_MEMBER_KEY)
        or snapshot.decision_grade_eligible
        or snapshot.deployment_authorized
    ):
        return False
    receipt_member, response_member = snapshot.members
    if (
        response_member.content_hash != request.expected_response_sha256
        or response_member.declared_sha256 != request.expected_response_sha256
        or receipt_member.declared_sha256 != receipt_member.content_hash
        or any(member.mode != "0644" for member in snapshot.members)
    ):
        return False
    try:
        receipt = snapshot.member_bytes(_RECEIPT_MEMBER_KEY)
        raw = snapshot.member_bytes(_RESPONSE_MEMBER_KEY)
        observed_at, acquired_at, _ = _receipt_facts(request, receipt, raw)
    except (RecursionError, ValueError):
        return False
    return (
        _sha256(raw) == request.expected_response_sha256
        and _sha256(receipt) == receipt_member.content_hash
        and snapshot.provenance == _provenance(request, observed_at)
        and all(
            member.acquired_at_epoch_nanoseconds == acquired_at
            for member in snapshot.members
        )
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureResultV1:
    request: BinanceUsdmKoruFundingRateHistorySourceBoundedRequestV1
    snapshot: SourceSnapshot
    attempts: int
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        trusted = _trusted_request(self.request)
        if (
            trusted is None
            or type(self.attempts) is not int
            or not 1 <= self.attempts <= _MAX_ATTEMPTS
            or not _snapshot_matches_request(trusted, self.snapshot)
        ):
            raise ValueError(
                "capture result must bind exact verified KORU funding evidence"
            )
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("development-only qualification flags must remain false")

    @property
    def capture_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_funding_rate_history_source_bounded_capture_result_v1",
            "schema_version": _SCHEMA_VERSION,
            "request": self.request.to_canonical_dict(),
            "request_hash": self.request.request_hash,
            "snapshot": self.snapshot.to_canonical_dict(),
            "source_snapshot_hash": canonical_sha256(self.snapshot.to_canonical_dict()),
            "attempts": self.attempts,
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


def _trusted_capture(
    value: object,
) -> BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureResultV1 | None:
    if type(value) is not BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureResultV1:
        return None
    try:
        rebuilt = BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureResultV1(
            value.request,
            value.snapshot,
            value.attempts,
            value.decision_grade_eligible,
            value.deployment_authorized,
        )
        if rebuilt.to_canonical_dict() != value.to_canonical_dict():
            return None
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureOutcomeV1:
    result: BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureResultV1 | None = None
    failure: BinanceUsdmKoruFundingRateHistorySourceBoundedFailureV1 | None = None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")
        if self.result is not None and _trusted_capture(self.result) is None:
            raise ValueError("capture outcome result is not canonical")
        if (
            self.failure is not None
            and type(self.failure)
            is not BinanceUsdmKoruFundingRateHistorySourceBoundedFailureV1
        ):
            raise TypeError("capture outcome failure must be exact")


def _fetch(
    url: str, fetch: FetchResponse
) -> tuple[
    BinanceUsdmKoruFundingRateHistoryTransportResponseV1 | None,
    int,
    BinanceUsdmKoruFundingRateHistorySourceBoundedFailureV1 | None,
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
                        BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.PROVIDER_UNAVAILABLE,
                        url,
                    ),
                )
            continue
        response = _trusted_transport_response(response)
        if (
            response is None
            or response.method != "GET"
            or response.requested_url != url
            or response.final_url != url
        ):
            return (
                None,
                attempt,
                _failure(
                    BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.CONFIGURATION_INVALID,
                    url,
                ),
            )
        if response.status == 200:
            return response, attempt, None
        if response.status in (401, 403):
            return (
                None,
                attempt,
                _failure(
                    BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.AUTHENTICATION_REJECTED,
                    url,
                ),
            )
        if response.status == 429:
            if attempt < _MAX_ATTEMPTS:
                continue
            return (
                None,
                attempt,
                _failure(
                    BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.RATE_LIMIT_EXHAUSTED,
                    url,
                ),
            )
        if 500 <= response.status <= 599:
            if attempt < _MAX_ATTEMPTS:
                continue
            return (
                None,
                attempt,
                _failure(
                    BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.PROVIDER_UNAVAILABLE,
                    url,
                ),
            )
        return (
            None,
            attempt,
            _failure(
                (
                    BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.DATA_GAP_DETECTED
                    if response.status == 404
                    else BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH
                ),
                url,
            ),
        )
    raise AssertionError("unreachable")


def capture_binance_usdm_koru_funding_rate_history_source_bounded_v1(
    request: BinanceUsdmKoruFundingRateHistorySourceBoundedRequestV1,
    fetch: FetchResponse,
) -> BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureOutcomeV1:
    trusted = _trusted_request(request)
    if trusted is None or not callable(fetch):
        return BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.CONFIGURATION_INVALID
            )
        )
    response, attempts, failure = _fetch(trusted.url, fetch)
    if failure is not None:
        return BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureOutcomeV1(
            failure=failure
        )
    if response is None:
        return BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.CONFIGURATION_INVALID
            )
        )
    raw = response.body
    if _sha256(raw) != trusted.expected_response_sha256:
        return BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH,
                trusted.url,
            )
        )
    try:
        observed_at = _date_header_nanoseconds(response.date_header)
        if observed_at < trusted.end_time_milliseconds * 1_000_000:
            raise ValueError("Date cannot precede request end")
        if response.acquired_at_epoch_nanoseconds < observed_at:
            raise ValueError("acquired_at cannot precede Date")
        parsed = _provider_json(raw)
        if type(parsed) is not list:
            raise ValueError("response must be an array")
        receipt = _receipt_bytes(trusted, response, len(cast(list[object], parsed)))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
        return BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
                _RESPONSE_MEMBER_KEY,
            )
        )
    frozen = freeze_source_snapshot(
        members=(
            RawSourceMember(
                _RECEIPT_MEMBER_KEY,
                receipt,
                "0644",
                response.acquired_at_epoch_nanoseconds,
                _sha256(receipt),
            ),
            RawSourceMember(
                _RESPONSE_MEMBER_KEY,
                raw,
                "0644",
                response.acquired_at_epoch_nanoseconds,
                trusted.expected_response_sha256,
            ),
        ),
        provenance=_provenance(trusted, observed_at),
    )
    if frozen.snapshot is None:
        return BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SNAPSHOT_INVALID
            )
        )
    try:
        result = BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureResultV1(
            trusted, frozen.snapshot, attempts
        )
    except (TypeError, ValueError):
        return BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureOutcomeV1(
            failure=_failure(
                BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SNAPSHOT_INVALID
            )
        )
    return BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureOutcomeV1(result=result)


class _NormalizationError(ValueError):
    def __init__(
        self,
        code: BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1,
        subject: str,
        row_number: int | None = None,
    ) -> None:
        super().__init__(subject)
        self.code: BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1 = code
        self.subject: str = subject
        self.row_number: int | None = row_number


@dataclass(frozen=True, slots=True)
class _ParsedRow:
    source_row: _SourceRow
    funding_rate_units: int
    mark_price_units: int
    source_record_hash: str


@dataclass(frozen=True, slots=True)
class _ReconstructedSource:
    observed_at_epoch_nanoseconds: int
    acquired_at_epoch_nanoseconds: int
    requested_start: UtcInstant
    requested_end_inclusive: UtcInstant
    coverage_start: UtcInstant
    coverage_end_exclusive: UtcInstant
    first_funding_time_milliseconds: int
    last_funding_time_milliseconds: int
    regular_count: int
    special_count: int
    missing_rate_type_count: int
    response_member_hash: str
    receipt_member_hash: str
    receipt_hash: str
    events: tuple[MarketEvent, ...]


def _decimal_units(value: str, *, positive: bool) -> int:
    pattern = _MARK if positive else _RATE
    if len(value) > 64 or pattern.fullmatch(value) is None:
        raise ValueError("non-canonical decimal")
    try:
        with localcontext() as context:
            context.prec = 100
            scaled = Decimal(value) * Decimal(10**_SCALE)
            integral = scaled.to_integral_value()
    except (InvalidOperation, ValueError) as error:
        raise ValueError("decimal normalization failed") from error
    if scaled != integral:
        raise ValueError("decimal cannot be represented at exact scale")
    try:
        units = int(integral)
    except (OverflowError, ValueError) as error:
        raise ValueError("decimal normalization failed") from error
    if positive and units <= 0:
        raise ValueError("mark price must be positive")
    if not positive and value.startswith("-") and units == 0:
        raise ValueError("negative zero is not canonical")
    return units


def _source_record_hash(row: _SourceRow) -> str:
    symbol, funding_time, funding_rate, mark_price, rate_type, type_present = row
    fields = (
        _RESPONSE_FIELDS_WITH_TYPE if type_present else _RESPONSE_FIELDS_WITHOUT_TYPE
    )
    values: tuple[object, ...] = (
        (symbol, funding_time, funding_rate, mark_price, rate_type)
        if type_present
        else (symbol, funding_time, funding_rate, mark_price)
    )
    return canonical_sha256({"fields": fields, "row": values})


def _parse_rows(raw: bytes) -> tuple[_ParsedRow, ...]:
    try:
        parsed = _provider_json(raw)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValueError,
    ) as error:
        raise _NormalizationError(
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "response_json",
        ) from error
    if type(parsed) is not list:
        raise _NormalizationError(
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "response_envelope",
        )
    parsed_rows = cast(list[object], parsed)
    if not parsed_rows:
        raise _NormalizationError(
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
            "row_count",
        )
    rows: list[_ParsedRow] = []
    for row_number, item in enumerate(parsed_rows, 1):
        if type(item) is not dict or tuple(item) not in (
            _RESPONSE_FIELDS_WITHOUT_TYPE,
            _RESPONSE_FIELDS_WITH_TYPE,
        ):
            raise _NormalizationError(
                BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
                "row_fields",
                row_number,
            )
        item_value = cast(dict[str, object], item)
        symbol = item_value["symbol"]
        funding_time = item_value["fundingTime"]
        funding_rate = item_value["fundingRate"]
        mark_price = item_value["markPrice"]
        type_present = "rateType" in item_value
        rate_type = item_value.get("rateType")
        if (
            type(symbol) is not str
            or type(funding_time) is not int
            or type(funding_rate) is not str
            or type(mark_price) is not str
            or (type_present and type(rate_type) is not str)
            or (not type_present and rate_type is not None)
        ):
            raise _NormalizationError(
                BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
                "row_primitives",
                row_number,
            )
        symbol_value = cast(str, symbol)
        funding_time_value = cast(int, funding_time)
        funding_rate_value = cast(str, funding_rate)
        mark_price_value = cast(str, mark_price)
        rate_type_value = cast(str | None, rate_type)
        if symbol_value != _SYMBOL:
            raise _NormalizationError(
                BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
                "symbol",
                row_number,
            )
        if type_present and rate_type_value not in ("Regular", "Special"):
            raise _NormalizationError(
                BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
                "rate_type",
                row_number,
            )
        try:
            time_value = _exact_milliseconds("fundingTime", funding_time_value)
            rate_units = _decimal_units(funding_rate_value, positive=False)
            mark_units = _decimal_units(mark_price_value, positive=True)
        except (TypeError, ValueError) as error:
            raise _NormalizationError(
                BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
                "row_value",
                row_number,
            ) from error
        source_row: _SourceRow = (
            symbol_value,
            time_value,
            funding_rate_value,
            mark_price_value,
            rate_type_value,
            type_present,
        )
        rows.append(
            _ParsedRow(
                source_row,
                rate_units,
                mark_units,
                _source_record_hash(source_row),
            )
        )
    return tuple(rows)


def _validated_rows(
    request: BinanceUsdmKoruFundingRateHistorySourceBoundedRequestV1,
    rows: tuple[_ParsedRow, ...],
) -> tuple[_ParsedRow, ...]:
    observed: dict[int, _SourceRow] = {}
    previous: _ParsedRow | None = None
    for row_number, current in enumerate(rows, 1):
        funding_time = current.source_row[1]
        duplicate = observed.get(funding_time)
        if duplicate is not None:
            raise _NormalizationError(
                BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.DUPLICATE_OR_CONFLICT,
                "duplicate_funding_slot"
                if duplicate == current.source_row
                else "conflicting_funding_slot",
                row_number,
            )
        observed[funding_time] = current.source_row
        if (
            not request.start_time_milliseconds
            <= funding_time
            <= request.end_time_milliseconds
        ):
            raise _NormalizationError(
                BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.DATA_GAP_DETECTED,
                "request_window",
                row_number,
            )
        if previous is not None and funding_time < previous.source_row[1]:
            raise _NormalizationError(
                BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.ORDER_VIOLATION,
                "funding_slot_order",
                row_number,
            )
        previous = current
    return rows


def _read_retained_evidence(
    capture: BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureResultV1,
) -> tuple[bytes, bytes, int, int]:
    try:
        receipt = capture.snapshot.member_bytes(_RECEIPT_MEMBER_KEY)
        raw = capture.snapshot.member_bytes(_RESPONSE_MEMBER_KEY)
        parsed = _provider_json(raw)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        ValueError,
    ) as error:
        raise _NormalizationError(
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "snapshot_member",
        ) from error
    if type(parsed) is not list:
        raise _NormalizationError(
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SOURCE_SCHEMA_MISMATCH,
            "response_envelope",
        )
    try:
        observed_at, acquired_at, _ = _receipt_facts(capture.request, receipt, raw)
    except ValueError as error:
        raise _NormalizationError(
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH,
            "retained_evidence",
        ) from error
    if (
        _sha256(raw) != capture.request.expected_response_sha256
        or _sha256(receipt) != capture.snapshot.members[0].content_hash
    ):
        raise _NormalizationError(
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.SOURCE_HASH_MISMATCH,
            "retained_evidence",
        )
    return receipt, raw, observed_at, acquired_at


def _event_from_row(
    capture: BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureResultV1,
    row: _ParsedRow,
    receipt_hash: str,
    observed_at_epoch_nanoseconds: int,
    acquired_at_epoch_nanoseconds: int,
) -> MarketEvent:
    request = capture.request
    receipt_member, response_member = capture.snapshot.members
    funding_time = row.source_row[1]
    snapshot_hash = canonical_sha256(capture.snapshot.to_canonical_dict())
    identity = {
        "type": "binance_usdm_koru_funding_rate_history_event_identity_v1",
        "schema_version": _SCHEMA_VERSION,
        "source_snapshot_id": capture.snapshot.snapshot_id,
        "funding_slot_milliseconds": funding_time,
        "source_record_hash": row.source_record_hash,
        "economic_policy_ref": _ECONOMIC_POLICY_REF,
    }
    payload = {
        "funding_purpose": "funding_publication",
        "funding_slot_milliseconds": funding_time,
        "funding_rate_units": row.funding_rate_units,
        "funding_rate_scale": _SCALE,
        "raw_funding_rate": row.source_row[2],
        "mark_price_units": row.mark_price_units,
        "mark_price_scale": _SCALE,
        "raw_mark_price": row.source_row[3],
        "rate_type": row.source_row[4],
        "source_record_hash": row.source_record_hash,
        "request_hash": request.request_hash,
        "capture_hash": capture.capture_hash,
        "source_snapshot_id": capture.snapshot.snapshot_id,
        "source_snapshot_hash": snapshot_hash,
        "source_provenance_hash": capture.snapshot.provenance_hash,
        "response_member_key": response_member.member_key,
        "response_member_hash": response_member.content_hash,
        "receipt_member_key": receipt_member.member_key,
        "receipt_member_hash": receipt_member.content_hash,
        "receipt_hash": receipt_hash,
        "economic_policy_ref": _ECONOMIC_POLICY_REF,
        "observed_at_epoch_nanoseconds": observed_at_epoch_nanoseconds,
        "acquired_at_epoch_nanoseconds": acquired_at_epoch_nanoseconds,
    }
    if frozenset(payload) != _EVENT_PAYLOAD_KEYS:
        raise AssertionError("event payload lineage is incomplete")
    effective = UtcInstant(funding_time * 1_000_000)
    return MarketEvent(
        event_id="binance-usdm-koru-funding-history-v1:" + canonical_sha256(identity),
        stream_key=_STREAM_KEY,
        event_type=_EVENT_TYPE,
        capability=_CAPABILITY,
        instrument_id=request.instrument_id,
        event_time=effective,
        available_time=effective,
        phase=_PHASE,
        source_sequence=SourceSequence(0),
        revision_id=response_member.content_hash,
        supersedes_revision_id=None,
        source_key=capture.snapshot.provenance.source_key,
        source_hash=response_member.content_hash,
        payload=payload,
    )


def _reconstruct_retained_source(
    capture: BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureResultV1,
) -> _ReconstructedSource:
    receipt, raw, observed_at, acquired_at = _read_retained_evidence(capture)
    rows = _validated_rows(capture.request, _parse_rows(raw))
    receipt_hash = _sha256(receipt)
    try:
        events = tuple(
            _event_from_row(capture, row, receipt_hash, observed_at, acquired_at)
            for row in rows
        )
    except (TypeError, ValueError) as error:
        raise _NormalizationError(
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
            "market_event",
        ) from error
    rate_types = tuple(row.source_row[4] for row in rows)
    first = rows[0].source_row[1]
    last = rows[-1].source_row[1]
    return _ReconstructedSource(
        observed_at_epoch_nanoseconds=observed_at,
        acquired_at_epoch_nanoseconds=acquired_at,
        requested_start=UtcInstant(capture.request.start_time_milliseconds * 1_000_000),
        requested_end_inclusive=UtcInstant(
            capture.request.end_time_milliseconds * 1_000_000
        ),
        coverage_start=UtcInstant(first * 1_000_000),
        coverage_end_exclusive=UtcInstant(last * 1_000_000 + 1),
        first_funding_time_milliseconds=first,
        last_funding_time_milliseconds=last,
        regular_count=rate_types.count("Regular"),
        special_count=rate_types.count("Special"),
        missing_rate_type_count=rate_types.count(None),
        response_member_hash=capture.snapshot.members[1].content_hash,
        receipt_member_hash=capture.snapshot.members[0].content_hash,
        receipt_hash=receipt_hash,
        events=events,
    )


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationResultV1:
    capture: BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureResultV1
    source_snapshot_id: str
    source_snapshot_hash: str
    request_hash: str
    capture_hash: str
    requested_start: UtcInstant
    requested_end_inclusive: UtcInstant
    coverage_start: UtcInstant
    coverage_end_exclusive: UtcInstant
    prefix_gap_classification: str
    suffix_gap_classification: str
    completeness_classification: str
    row_count: int
    first_funding_time_milliseconds: int
    last_funding_time_milliseconds: int
    regular_count: int
    special_count: int
    missing_rate_type_count: int
    response_member_hash: str
    receipt_member_hash: str
    receipt_hash: str
    economic_policy_ref: str
    events: tuple[MarketEvent, ...]
    decision_grade_eligible: bool = False
    deployment_authorized: bool = False

    def __post_init__(self) -> None:
        trusted = _trusted_capture(self.capture)
        if trusted is None:
            raise ValueError("normalization result capture is not canonical")
        try:
            rebuilt = _reconstruct_retained_source(trusted)
        except _NormalizationError as error:
            raise ValueError(
                "normalization result cannot reconstruct retained source"
            ) from error
        expected = {
            "source_snapshot_id": trusted.snapshot.snapshot_id,
            "source_snapshot_hash": canonical_sha256(
                trusted.snapshot.to_canonical_dict()
            ),
            "request_hash": trusted.request.request_hash,
            "capture_hash": trusted.capture_hash,
            "requested_start": rebuilt.requested_start,
            "requested_end_inclusive": rebuilt.requested_end_inclusive,
            "coverage_start": rebuilt.coverage_start,
            "coverage_end_exclusive": rebuilt.coverage_end_exclusive,
            "prefix_gap_classification": _PREFIX_CLASSIFICATION,
            "suffix_gap_classification": _SUFFIX_CLASSIFICATION,
            "completeness_classification": _COMPLETENESS_CLASSIFICATION,
            "row_count": len(rebuilt.events),
            "first_funding_time_milliseconds": rebuilt.first_funding_time_milliseconds,
            "last_funding_time_milliseconds": rebuilt.last_funding_time_milliseconds,
            "regular_count": rebuilt.regular_count,
            "special_count": rebuilt.special_count,
            "missing_rate_type_count": rebuilt.missing_rate_type_count,
            "response_member_hash": rebuilt.response_member_hash,
            "receipt_member_hash": rebuilt.receipt_member_hash,
            "receipt_hash": rebuilt.receipt_hash,
            "economic_policy_ref": _ECONOMIC_POLICY_REF,
            "events": rebuilt.events,
        }
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError(
                "normalization result fields do not exactly reconstruct source"
            )
        if (
            type(self.events) is not tuple
            or any(type(event) is not MarketEvent for event in self.events)
            or [event.to_canonical_dict() for event in self.events]
            != [event.to_canonical_dict() for event in rebuilt.events]
        ):
            raise ValueError(
                "normalization result events do not exactly reconstruct source"
            )
        integer_fields = (
            self.row_count,
            self.first_funding_time_milliseconds,
            self.last_funding_time_milliseconds,
            self.regular_count,
            self.special_count,
            self.missing_rate_type_count,
        )
        if any(type(value) is not int for value in integer_fields):
            raise ValueError("normalization result counts must be exact integers")
        if self.decision_grade_eligible or self.deployment_authorized:
            raise ValueError("development-only qualification flags must remain false")

    @property
    def normalization_hash(self) -> str:
        return canonical_sha256(self.to_canonical_dict())

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "binance_usdm_koru_funding_rate_history_source_bounded_normalization_result_v1",
            "schema_version": _SCHEMA_VERSION,
            "source_snapshot_id": self.source_snapshot_id,
            "source_snapshot_hash": self.source_snapshot_hash,
            "request_hash": self.request_hash,
            "capture_hash": self.capture_hash,
            "requested_start": self.requested_start.to_canonical_dict(),
            "requested_end_inclusive": self.requested_end_inclusive.to_canonical_dict(),
            "coverage_start": self.coverage_start.to_canonical_dict(),
            "coverage_end_exclusive": self.coverage_end_exclusive.to_canonical_dict(),
            "prefix_gap_classification": self.prefix_gap_classification,
            "suffix_gap_classification": self.suffix_gap_classification,
            "completeness_classification": self.completeness_classification,
            "row_count": self.row_count,
            "first_funding_time_milliseconds": self.first_funding_time_milliseconds,
            "last_funding_time_milliseconds": self.last_funding_time_milliseconds,
            "regular_count": self.regular_count,
            "special_count": self.special_count,
            "missing_rate_type_count": self.missing_rate_type_count,
            "response_member_hash": self.response_member_hash,
            "receipt_member_hash": self.receipt_member_hash,
            "receipt_hash": self.receipt_hash,
            "economic_policy_ref": self.economic_policy_ref,
            "events": [event.to_canonical_dict() for event in self.events],
            "decision_grade_eligible": self.decision_grade_eligible,
            "deployment_authorized": self.deployment_authorized,
        }


def _trusted_normalization_result(
    value: object,
) -> BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationResultV1 | None:
    if (
        type(value)
        is not BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationResultV1
    ):
        return None
    try:
        values = cast(
            BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationResultV1, value
        )
        rebuilt = BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationResultV1(
            capture=values.capture,
            source_snapshot_id=values.source_snapshot_id,
            source_snapshot_hash=values.source_snapshot_hash,
            request_hash=values.request_hash,
            capture_hash=values.capture_hash,
            requested_start=values.requested_start,
            requested_end_inclusive=values.requested_end_inclusive,
            coverage_start=values.coverage_start,
            coverage_end_exclusive=values.coverage_end_exclusive,
            prefix_gap_classification=values.prefix_gap_classification,
            suffix_gap_classification=values.suffix_gap_classification,
            completeness_classification=values.completeness_classification,
            row_count=values.row_count,
            first_funding_time_milliseconds=values.first_funding_time_milliseconds,
            last_funding_time_milliseconds=values.last_funding_time_milliseconds,
            regular_count=values.regular_count,
            special_count=values.special_count,
            missing_rate_type_count=values.missing_rate_type_count,
            response_member_hash=values.response_member_hash,
            receipt_member_hash=values.receipt_member_hash,
            receipt_hash=values.receipt_hash,
            economic_policy_ref=values.economic_policy_ref,
            events=values.events,
            decision_grade_eligible=values.decision_grade_eligible,
            deployment_authorized=values.deployment_authorized,
        )
        if rebuilt.to_canonical_dict() != values.to_canonical_dict():
            return None
    except (AttributeError, TypeError, ValueError):
        return None
    return rebuilt


@dataclass(frozen=True, slots=True)
class BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationOutcomeV1:
    result: (
        BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationResultV1 | None
    ) = None
    failure: BinanceUsdmKoruFundingRateHistorySourceBoundedFailureV1 | None = None

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
            and type(self.failure)
            is not BinanceUsdmKoruFundingRateHistorySourceBoundedFailureV1
        ):
            raise TypeError("normalization outcome failure must be exact")


def _normalization_failure(
    code: BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1,
    subject: str,
    row_number: int | None = None,
) -> BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationOutcomeV1:
    return BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationOutcomeV1(
        failure=_failure(code, subject, row_number)
    )


def normalize_binance_usdm_koru_funding_rate_history_source_bounded_v1(
    capture: BinanceUsdmKoruFundingRateHistorySourceBoundedCaptureResultV1,
) -> BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationOutcomeV1:
    trusted = _trusted_capture(capture)
    if trusted is None:
        return _normalization_failure(
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.CONFIGURATION_INVALID,
            "capture",
        )
    try:
        rebuilt = _reconstruct_retained_source(trusted)
        result = BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationResultV1(
            capture=trusted,
            source_snapshot_id=trusted.snapshot.snapshot_id,
            source_snapshot_hash=canonical_sha256(trusted.snapshot.to_canonical_dict()),
            request_hash=trusted.request.request_hash,
            capture_hash=trusted.capture_hash,
            requested_start=rebuilt.requested_start,
            requested_end_inclusive=rebuilt.requested_end_inclusive,
            coverage_start=rebuilt.coverage_start,
            coverage_end_exclusive=rebuilt.coverage_end_exclusive,
            prefix_gap_classification=_PREFIX_CLASSIFICATION,
            suffix_gap_classification=_SUFFIX_CLASSIFICATION,
            completeness_classification=_COMPLETENESS_CLASSIFICATION,
            row_count=len(rebuilt.events),
            first_funding_time_milliseconds=rebuilt.first_funding_time_milliseconds,
            last_funding_time_milliseconds=rebuilt.last_funding_time_milliseconds,
            regular_count=rebuilt.regular_count,
            special_count=rebuilt.special_count,
            missing_rate_type_count=rebuilt.missing_rate_type_count,
            response_member_hash=rebuilt.response_member_hash,
            receipt_member_hash=rebuilt.receipt_member_hash,
            receipt_hash=rebuilt.receipt_hash,
            economic_policy_ref=_ECONOMIC_POLICY_REF,
            events=rebuilt.events,
        )
    except _NormalizationError as error:
        return _normalization_failure(error.code, error.subject, error.row_number)
    except (TypeError, ValueError):
        return _normalization_failure(
            BinanceUsdmKoruFundingRateHistorySourceBoundedFailureCodeV1.NORMALIZATION_FAILED,
            "normalization_result",
        )
    return BinanceUsdmKoruFundingRateHistorySourceBoundedNormalizationOutcomeV1(
        result=result
    )
