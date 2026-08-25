from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from html import unescape
from typing import Any, cast

from crypto_quant_domain import ArtifactEnvelope, ArtifactRef, canonical_bytes

from .source_snapshots import (
    RawSourceMember,
    SourceSnapshot,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)

_SCHEMA_VERSION = 1
_COVERAGE_START = "2026-07-15T10:00:00Z"
_COVERAGE_END_EXCLUSIVE = "2026-10-05T00:00:00Z"
_MEMBER_HASHES = {
    "binance/acquisition-receipt.json": "sha256:e37c33eaf1b85c800f225b5d1f798069992772084b21ed91384af8f242173e59",
    "binance/adjustment-announcement.json": "sha256:0f06a75fa2b8291ee8ec1c749657576467a84092fa096ece181958069acae97e",
    "binance/completion-announcement.json": "sha256:c194651673fbd80c014c8e3931403f6a51d14cb8bf920fcf17c0c3e609c9a143",
    "krx/acquisition-receipt.json": "sha256:414c889f216f01be161110d4116bd4cd26509d4ec1079a32c043d62f9cee4f58",
    "krx/landing.html": "sha256:c181b15a7c08cc48a4fc390160cdf748c3680006155f1a0124465613f32b978e",
    "krx/market-closing-2026.json": "sha256:e60dc5a3d4f8a02afc842f34544f2edf162836bc124209b75dc7456030858dfe",
    "nyse/acquisition-receipt.json": "sha256:a393aaa8efe6e9747711695d0df2c49d98cd56ef9ad3ba83ed75d15f613a273c",
    "nyse/hours-calendars.html": "sha256:49ee8a651ec01ef2866e347842c0fb11309541f247d17aeaaf7ad9d6a513b1ed",
}
APPROVED_MEMBER_HASHES = tuple(sorted(_MEMBER_HASHES.items()))
_PROVENANCE = SourceSnapshotProvenance(
    vendor_key="krx.nyse.binance",
    source_key="koru.tradifi.calendar-unit-authority.v1",
    license_ref="source-site-terms",
    retention_policy_ref="immutable-development-fixture",
)
_KRX_ARTIFACT = "xkrx_regular_session_calendar"
_ARCX_ARTIFACT = "arcx_koru_core_session_calendar"
_UNIT_ARTIFACT = "binance_usdm_tradifi_post_adjustment_unit_regime"
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_KRX_ROW_KEYS = {
    "calnd_dd",
    "dy_tp_cd",
    "calnd_dd_dy",
    "kr_dy_tp",
    "holdy_eng_nm",
}
_WEEKDAYS = (
    ("MON", "Monday"),
    ("TUE", "Tuesday"),
    ("WED", "Wednesday"),
    ("THU", "Thursday"),
    ("FRI", "Friday"),
    ("SAT", "Saturday"),
    ("SUN", "Sunday"),
)
_KRX_CLOSURES = (
    ("2026-01-01", "New Year's Day"),
    ("2026-02-16", "Seollal (New Year's Day by the lunar)"),
    ("2026-02-17", "Seollal (New Year's Day by the lunar)"),
    ("2026-02-18", "Seollal (New Year's Day by the lunar)"),
    ("2026-03-02", "Substitution Holiday"),
    ("2026-05-01", "Labor Day"),
    ("2026-05-05", "Children's Day"),
    ("2026-05-25", "Substitution Holiday"),
    ("2026-06-03", "Temporary Holiday"),
    ("2026-07-17", ""),
    ("2026-08-17", "Substitution Holiday"),
    ("2026-09-24", "Chuseok (Korean Thanksgiving)"),
    ("2026-09-25", "Chuseok (Korean Thanksgiving)"),
    ("2026-10-05", "Substitution Holiday"),
    ("2026-10-09", "Hangeul Proclamation Day"),
    ("2026-12-25", "Christmas Day"),
    ("2026-12-31", "End of Year Holiday"),
)
_NYSE_2026_CLOSURES = (
    ("2026-01-01", "New Year’s Day"),
    ("2026-01-19", "Martin Luther King, Jr. Day"),
    ("2026-02-16", "Washington's Birthday"),
    ("2026-04-03", "Good Friday"),
    ("2026-05-25", "Memorial Day"),
    ("2026-06-19", "Juneteenth National Independence Day"),
    ("2026-07-03", "Independence Day observed"),
    ("2026-09-07", "Labor Day"),
    ("2026-11-26", "Thanksgiving Day"),
    ("2026-12-25", "Christmas Day"),
)
_KRX_LIMITATIONS = (
    "development_only",
    "official_krx_capture_may_be_revised_after_acquisition",
    "regular_session_windows_only",
)
_ARCX_LIMITATIONS = (
    "development_only",
    "official_nyse_page_capture_may_be_revised_after_acquisition",
    "nyse_arca_core_session_windows_only",
)
_UNIT_LIMITATIONS = (
    "development_only",
    "post_adjustment_single_unit_regime_only",
    "pre_adjustment_and_cross_regime_admission_prohibited",
)


class KoruTradifiCalendarUnitAuthorityFailureCode(str, Enum):
    INVALID_INPUT = "invalid_input"
    SOURCE_SNAPSHOT_INVALID = "source_snapshot_invalid"
    RECEIPT_INVALID = "receipt_invalid"
    SOURCE_SCHEMA_MISMATCH = "source_schema_mismatch"
    SOURCE_ATTESTATION_MISMATCH = "source_attestation_mismatch"
    RESULT_MISMATCH = "result_mismatch"


@dataclass(frozen=True, slots=True)
class KoruTradifiCalendarUnitAuthorityFailureV1:
    code: KoruTradifiCalendarUnitAuthorityFailureCode
    member_key: str | None = None

    def __post_init__(self) -> None:
        if type(self.code) is not KoruTradifiCalendarUnitAuthorityFailureCode:
            raise TypeError("code must be exact authority failure code")
        if self.member_key is not None and self.member_key not in _MEMBER_HASHES:
            raise ValueError("member_key must be an authority member")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_tradifi_calendar_unit_authority_failure_v1",
            "schema_version": _SCHEMA_VERSION,
            "code": self.code.value,
            "member_key": self.member_key,
        }


@dataclass(frozen=True, slots=True)
class KoruTradifiCalendarUnitAuthorityResultV1:
    source_snapshot: SourceSnapshot
    xkrx_calendar: ArtifactEnvelope
    arcx_calendar: ArtifactEnvelope
    post_adjustment_unit_regime: ArtifactEnvelope
    xkrx_calendar_ref: ArtifactRef
    arcx_calendar_ref: ArtifactRef
    post_adjustment_unit_regime_ref: ArtifactRef

    def __post_init__(self) -> None:
        if type(self.source_snapshot) is not SourceSnapshot:
            raise TypeError("source_snapshot must be exact SourceSnapshot")
        expected = (
            (self.xkrx_calendar, self.xkrx_calendar_ref, _KRX_ARTIFACT),
            (self.arcx_calendar, self.arcx_calendar_ref, _ARCX_ARTIFACT),
            (
                self.post_adjustment_unit_regime,
                self.post_adjustment_unit_regime_ref,
                _UNIT_ARTIFACT,
            ),
        )
        for envelope, ref, artifact_type in expected:
            if type(envelope) is not ArtifactEnvelope or type(ref) is not ArtifactRef:
                raise TypeError("artifacts and refs must be exact domain values")
            if (
                envelope.artifact_type != artifact_type
                or envelope.schema_version != _SCHEMA_VERSION
                or ref != ArtifactRef.from_envelope(envelope)
            ):
                raise ValueError("artifact/ref identity mismatch")

    @property
    def artifacts(self) -> tuple[ArtifactEnvelope, ArtifactEnvelope, ArtifactEnvelope]:
        return (
            self.xkrx_calendar,
            self.arcx_calendar,
            self.post_adjustment_unit_regime,
        )

    @property
    def refs(self) -> tuple[ArtifactRef, ArtifactRef, ArtifactRef]:
        return (
            self.xkrx_calendar_ref,
            self.arcx_calendar_ref,
            self.post_adjustment_unit_regime_ref,
        )

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "koru_tradifi_calendar_unit_authority_result_v1",
            "schema_version": _SCHEMA_VERSION,
            "source_snapshot": self.source_snapshot,
            "artifacts": self.artifacts,
            "refs": self.refs,
        }


@dataclass(frozen=True, slots=True)
class KoruTradifiCalendarUnitAuthorityOutcomeV1:
    result: KoruTradifiCalendarUnitAuthorityResultV1 | None
    failure: KoruTradifiCalendarUnitAuthorityFailureV1 | None

    def __post_init__(self) -> None:
        if (self.result is None) == (self.failure is None):
            raise ValueError("outcome must contain exactly one branch")


def _failed(
    code: KoruTradifiCalendarUnitAuthorityFailureCode,
    member_key: str | None = None,
) -> KoruTradifiCalendarUnitAuthorityOutcomeV1:
    return KoruTradifiCalendarUnitAuthorityOutcomeV1(
        None, KoruTradifiCalendarUnitAuthorityFailureV1(code, member_key)
    )


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in values:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _decode_json(source: bytes) -> dict[str, Any]:
    try:
        value = json.loads(source, object_pairs_hook=_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        raise ValueError("source JSON is invalid") from error
    if type(value) is not dict:
        raise ValueError("source JSON must be one object")
    return value


def _exact_keys(value: dict[str, Any], keys: set[str]) -> None:
    if set(value) != keys:
        raise ValueError("source schema mismatch")


def _receipt_time_ns(value: object) -> int:
    if type(value) is not str:
        raise ValueError("receipt capture time mismatch")
    match = re.fullmatch(r"(2026)-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)\.(\d{3})Z", value)
    if match is None:
        raise ValueError("receipt capture time mismatch")
    _, month, day, hour, minute, second, milliseconds = map(int, match.groups())
    epoch = date(1970, 1, 1)
    days = (date(2026, month, day) - epoch).days
    return (
        ((days * 24 + hour) * 60 + minute) * 60 + second
    ) * 1_000_000_000 + milliseconds * 1_000_000


def _member_map(snapshot: SourceSnapshot) -> dict[str, bytes]:
    return {
        member.member_key: snapshot.member_bytes(member.member_key)
        for member in snapshot.members
    }


def _source_binding(
    snapshot: SourceSnapshot,
    member_keys: tuple[str, ...],
    receipt: dict[str, Any],
) -> dict[str, object]:
    by_key = {member.member_key: member for member in snapshot.members}
    return {
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_content_tree_hash": snapshot.content_tree_hash,
        "snapshot_provenance_hash": snapshot.provenance_hash,
        "members": [
            {
                "member_key": key,
                "content_hash": by_key[key].content_hash,
                "byte_count": by_key[key].byte_count,
                "acquired_at_epoch_nanoseconds": by_key[
                    key
                ].acquired_at_epoch_nanoseconds,
                "declared_sha256": by_key[key].declared_sha256,
            }
            for key in member_keys
        ],
        "acquisition_receipt": receipt,
    }


def _validate_member_times(
    snapshot: SourceSnapshot, member_keys: tuple[str, ...], captured_at: object
) -> None:
    expected = _receipt_time_ns(captured_at)
    by_key = {member.member_key: member for member in snapshot.members}
    if any(
        by_key[key].acquired_at_epoch_nanoseconds != expected for key in member_keys
    ):
        raise ValueError("snapshot acquisition time does not match receipt")


def _parse_krx(
    members: dict[str, bytes], snapshot: SourceSnapshot
) -> tuple[tuple[tuple[str, str], ...], dict[str, Any]]:
    receipt = _decode_json(members["krx/acquisition-receipt.json"])
    _exact_keys(
        receipt,
        {
            "byte_count",
            "captured_at_utc",
            "date_header",
            "endpoint_url",
            "landing_date_header",
            "landing_sha256",
            "landing_url",
            "method",
            "record_count",
            "request",
            "response_sha256",
            "schema_version",
            "status",
            "type",
        },
    )
    if receipt != {
        "byte_count": 2221,
        "captured_at_utc": "2026-08-25T09:44:42.170Z",
        "date_header": "Tue, 25 Aug 2026 09:44:42 GMT",
        "endpoint_url": "http://global.krx.co.kr/contents/GLB/99/GLB99000001.jspx",
        "landing_date_header": "Tue, 25 Aug 2026 09:44:39 GMT",
        "landing_sha256": _MEMBER_HASHES["krx/landing.html"],
        "landing_url": "http://global.krx.co.kr/contents/GLB/05/0501/0501110000/GLB0501110000.jsp",
        "method": "POST",
        "record_count": 17,
        "request": {
            "bld": "GLB/05/0501/0501110000/glb0501110000_01",
            "gridTp": "KRX",
            "search_bas_yy": "2026",
        },
        "response_sha256": _MEMBER_HASHES["krx/market-closing-2026.json"],
        "schema_version": 1,
        "status": 200,
        "type": "krx_market_closing_2026_capture_receipt_v1",
    }:
        raise ValueError("KRX receipt mismatch")
    _validate_member_times(
        snapshot,
        (
            "krx/acquisition-receipt.json",
            "krx/landing.html",
            "krx/market-closing-2026.json",
        ),
        receipt["captured_at_utc"],
    )
    landing = members["krx/landing.html"]
    for marker in (
        b"Global KRX | KRX Market | Market Status | Market Closing(Holiday)",
        b'action="/contents/GLB/99/GLB99000001.jspx" method="post"',
        b'data-bld="GLB/05/0501/0501110000/glb0501110000_01"',
        b'<option value="2026" selected="selected">2026</option>',
    ):
        if marker not in landing:
            raise ValueError("KRX landing identity mismatch")
    response = _decode_json(members["krx/market-closing-2026.json"])
    _exact_keys(response, {"block1"})
    rows = response["block1"]
    if type(rows) is not list or len(rows) != 17:
        raise ValueError("KRX rows mismatch")
    closures: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if type(row) is not dict:
            raise ValueError("KRX row mismatch")
        _exact_keys(row, _KRX_ROW_KEYS)
        values = cast(dict[str, object], row)
        source_date = values["calnd_dd"]
        if (
            type(source_date) is not str
            or values["calnd_dd_dy"] != source_date
            or source_date in seen
            or type(values["holdy_eng_nm"]) is not str
        ):
            raise ValueError("KRX duplicate/date mismatch")
        parsed = date.fromisoformat(source_date)
        day_code, day_name = _WEEKDAYS[parsed.weekday()]
        if values["dy_tp_cd"] != day_code or values["kr_dy_tp"] != day_name:
            raise ValueError("KRX weekday mismatch")
        seen.add(source_date)
        closures.append((source_date, cast(str, values["holdy_eng_nm"])))
    result = tuple(closures)
    if result != _KRX_CLOSURES:
        raise ValueError("KRX closure authority mismatch")
    return result, receipt


def _parse_nyse(
    members: dict[str, bytes], snapshot: SourceSnapshot
) -> tuple[tuple[tuple[str, str], ...], dict[str, Any]]:
    receipt = _decode_json(members["nyse/acquisition-receipt.json"])
    _exact_keys(
        receipt,
        {
            "byte_count",
            "captured_at_utc",
            "date_header",
            "final_url",
            "method",
            "response_sha256",
            "schema_version",
            "status",
            "type",
            "url",
        },
    )
    if receipt != {
        "byte_count": 109180,
        "captured_at_utc": "2026-08-25T09:44:43.172Z",
        "date_header": "Tue, 25 Aug 2026 09:44:42 GMT",
        "final_url": "https://www.nyse.com/trade/hours-calendars",
        "method": "GET",
        "response_sha256": _MEMBER_HASHES["nyse/hours-calendars.html"],
        "schema_version": 1,
        "status": 200,
        "type": "nyse_hours_calendars_capture_receipt_v1",
        "url": "https://www.nyse.com/trade/hours-calendars",
    }:
        raise ValueError("NYSE receipt mismatch")
    _validate_member_times(
        snapshot,
        ("nyse/acquisition-receipt.json", "nyse/hours-calendars.html"),
        receipt["captured_at_utc"],
    )
    page = unescape(members["nyse/hours-calendars.html"].decode("utf-8"))
    holiday_table = (
        "<th>Holiday</th><th>2026</th><th>2027</th><th>2028</th>"
        "</tr></thead><tbody><tr><th>New Year’s Day</th><td>Thursday, January 1</td>"
    )
    labor_row = (
        "<tr><th>Labor Day</th><td>Monday, September 7</td>"
        "<td>Monday, September 6</td><td>Monday, September 4</td></tr>"
    )
    arca = page.find('<span class="pl-2">NYSE Arca Equities</span>')
    arca_core = page.find("Core Trading Session: 9:30 a.m. to 4:00 p.m. ET", arca)
    if (
        "<title>Holidays & Trading Hours</title>" not in page
        or '"urlPath":"/trade/hours-calendars"' not in page
        or holiday_table not in page
        or labor_row not in page
        or "Friday, November 27, 2026" not in page
        or "Thursday, December 24, 2026" not in page
        or arca < 0
        or arca_core < arca
        or arca_core > arca + 2_500
    ):
        raise ValueError("NYSE page attestation mismatch")
    return _NYSE_2026_CLOSURES, receipt


def _body_text(body: object) -> tuple[str, ...]:
    result: list[str] = []

    def visit(value: object) -> None:
        if type(value) is dict:
            item = cast(dict[str, object], value)
            if item.get("node") == "text":
                text = item.get("text")
                if type(text) is not str:
                    raise ValueError("Binance body text node mismatch")
                if text.strip():
                    result.append(unescape(text).replace("\xa0", " ").strip())
            for child in item.values():
                visit(child)
        elif type(value) is list:
            for child in cast(list[object], value):
                visit(child)
        elif value is not None and type(value) not in (str, int, bool):
            raise ValueError("Binance body schema mismatch")

    visit(body)
    return tuple(result)


def _parse_cms(
    source: bytes, expected_code: str, expected_title: str
) -> tuple[dict[str, Any], str]:
    document = _decode_json(source)
    _exact_keys(document, {"code", "message", "messageDetail", "data", "success"})
    data = document["data"]
    success = document["success"]
    if (
        document["code"] != "000000"
        or type(success) is not bool
        or not success
        or type(data) is not dict
    ):
        raise ValueError("Binance CMS response mismatch")
    _exact_keys(
        data,
        {
            "id",
            "title",
            "body",
            "code",
            "publishDate",
            "relatedArticles",
            "articleType",
            "firstCatalogName",
            "firstCatalogId",
            "secondCatalogName",
            "secondCatalogId",
            "thirdCatalogName",
            "thirdCatalogId",
            "seoTitle",
            "seoKeywords",
            "seoDesc",
            "version",
            "shareCount",
            "riskWarning",
            "footer",
            "contentJson",
            "pairs",
            "lastUpdateTime",
        },
    )
    if (
        data["code"] != expected_code
        or data["title"] != expected_title
        or data["seoTitle"] != expected_title
        or data["firstCatalogName"] != "Latest Binance News"
        or type(data["body"]) is not str
    ):
        raise ValueError("Binance CMS article identity mismatch")
    body = _decode_json(cast(str, data["body"]).encode("utf-8"))
    if body.get("node") != "root" or set(body) != {"node", "child"}:
        raise ValueError("Binance CMS body schema mismatch")
    text = "\n".join(_body_text(body))
    return data, text


def _parse_binance(
    members: dict[str, bytes], snapshot: SourceSnapshot
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    receipt = _decode_json(members["binance/acquisition-receipt.json"])
    _exact_keys(receipt, {"captured_at_utc", "records", "schema_version", "type"})
    records = receipt["records"]
    if (
        receipt["captured_at_utc"] != "2026-08-25T09:47:14.087Z"
        or receipt["schema_version"] != 1
        or receipt["type"] != "binance_koru_contract_adjustment_capture_receipt_v1"
        or type(records) is not list
        or len(records) != 2
    ):
        raise ValueError("Binance receipt mismatch")
    expected_records = (
        (
            "c226162366c54b78a7f98021b38e10c5",
            111662,
            "adjustment-announcement",
            "binance/adjustment-announcement.json",
        ),
        (
            "2ce887ba8fe14fdaa088e5bed7553a4e",
            68643,
            "completion-announcement",
            "binance/completion-announcement.json",
        ),
    )
    for record, (code, count, label, member_key) in zip(
        records, expected_records, strict=True
    ):
        if type(record) is not dict:
            raise ValueError("Binance receipt record mismatch")
        _exact_keys(
            record,
            {
                "article_code",
                "byte_count",
                "date_header",
                "final_url",
                "label",
                "method",
                "path",
                "sha256",
                "status",
                "url",
            },
        )
        url = (
            "https://www.binance.com/bapi/composite/v1/public/cms/article/detail/query"
            f"?articleCode={code}"
        )
        if record != {
            "article_code": code,
            "byte_count": count,
            "date_header": "Tue, 25 Aug 2026 09:46:00 GMT",
            "final_url": url,
            "label": label,
            "method": "GET",
            "path": "tests/fixtures/market_data/providers/tradifi/koru-calendar-unit-v1/"
            + member_key,
            "sha256": _MEMBER_HASHES[member_key],
            "status": 200,
            "url": url,
        }:
            raise ValueError("Binance receipt record mismatch")
    _validate_member_times(
        snapshot,
        (
            "binance/acquisition-receipt.json",
            "binance/adjustment-announcement.json",
            "binance/completion-announcement.json",
        ),
        receipt["captured_at_utc"],
    )
    adjustment, adjustment_text = _parse_cms(
        members["binance/adjustment-announcement.json"],
        "c226162366c54b78a7f98021b38e10c5",
        "Binance Futures Will Adjust The Contract Size of USDⓈ-Margined KORUUSDT Perpetual Contract (2026-07-15)",
    )
    completion, completion_text = _parse_cms(
        members["binance/completion-announcement.json"],
        "2ce887ba8fe14fdaa088e5bed7553a4e",
        "Binance Futures Has Completed USDⓈ-Margined KORUUSDT Perpetual Contract’s Contract Size Adjustment (2026-07-15)",
    )
    for marker in (
        "KORUUSDT Perpetual Contract commencing at\n2026-07-15 00:15 (UTC)",
        "A 20-for-1 forward share split",
        "Adjustment Scale Factor\n20",
        "800/20 = 40",
        "20 * 20 = 400",
    ):
        if marker not in adjustment_text:
            raise ValueError("Binance adjustment body attestation mismatch")
    for marker in (
        "2026-07-15 00:15 (UTC)  to 2026-07-15 09:30 (UTC)",
        "2026-07-15 09:30 (UTC) to 2026-07-15 09:35 (UTC)",
        "After 2026-07-15 09:35 (UTC)",
        "TRADING_HALT (Halt Session State)",
        "TRADING_CANCEL_ONLY (Cancel Only Session State)",
        "TRADING (Continuous Trading Session State)",
    ):
        if marker not in completion_text:
            raise ValueError("Binance completion body attestation mismatch")
    return adjustment, completion, receipt


def _iso(day: date, time: str) -> str:
    return f"{day.isoformat()}T{time}Z"


def _sessions(
    *,
    closures: set[str],
    open_time: str,
    close_time: str,
    local_open: str,
    local_close: str,
    source_timezone: str,
    utc_offset: str,
    dst_state: str,
) -> list[dict[str, str]]:
    start = date(2026, 7, 15)
    end = date(2026, 10, 5)
    result: list[dict[str, str]] = []
    current = start
    while current < end:
        source_date = current.isoformat()
        if current.weekday() < 5 and source_date not in closures:
            open_utc = _iso(current, open_time)
            close_utc = _iso(current, close_time)
            if open_utc >= _COVERAGE_START and close_utc <= _COVERAGE_END_EXCLUSIVE:
                result.append(
                    {
                        "session_date": source_date,
                        "open_utc": open_utc,
                        "close_utc": close_utc,
                        "source_local_open": f"{source_date}T{local_open}",
                        "source_local_close": f"{source_date}T{local_close}",
                        "source_timezone": source_timezone,
                        "utc_offset": utc_offset,
                        "dst_state": dst_state,
                    }
                )
        current += timedelta(days=1)
    _validate_sessions(result)
    return result


def _validate_sessions(sessions: list[dict[str, str]]) -> None:
    previous_close: str | None = None
    for session in sessions:
        opened = session["open_utc"]
        closed = session["close_utc"]
        if not _COVERAGE_START <= opened < closed <= _COVERAGE_END_EXCLUSIVE or (
            previous_close is not None and opened < previous_close
        ):
            raise ValueError("calendar sessions invalid")
        previous_close = closed


def _calendar_payloads(
    snapshot: SourceSnapshot,
    krx_closures: tuple[tuple[str, str], ...],
    krx_receipt: dict[str, Any],
    nyse_closures: tuple[tuple[str, str], ...],
    nyse_receipt: dict[str, Any],
) -> tuple[dict[str, object], dict[str, object]]:
    coverage = {"start": _COVERAGE_START, "end_exclusive": _COVERAGE_END_EXCLUSIVE}
    krx_sessions = _sessions(
        closures={value[0] for value in krx_closures},
        open_time="00:00:00",
        close_time="06:30:00",
        local_open="09:00:00",
        local_close="15:30:00",
        source_timezone="Asia/Seoul",
        utc_offset="+09:00",
        dst_state="not_observed",
    )
    arcx_sessions = _sessions(
        closures={value[0] for value in nyse_closures},
        open_time="13:30:00",
        close_time="20:00:00",
        local_open="09:30:00",
        local_close="16:00:00",
        source_timezone="America/New_York",
        utc_offset="-04:00",
        dst_state="EDT",
    )
    xkrx = {
        "type": "xkrx_regular_session_calendar_v1",
        "schema_version": 1,
        "venue": "XKRX",
        "session_kind": "regular",
        "coverage": coverage,
        "source_timezone": "Asia/Seoul",
        "source_utc_offset": "+09:00",
        "source_dst_observance": "none",
        "source_local_regular_hours": {"open": "09:00:00", "close": "15:30:00"},
        "source_closures_2026": [
            {"date": day, "reason": reason} for day, reason in krx_closures
        ],
        "applied_closure_dates": [
            "2026-07-17",
            "2026-08-17",
            "2026-09-24",
            "2026-09-25",
        ],
        "source_retained_not_emitted_boundary_closure_dates": ["2026-10-05"],
        "sessions": krx_sessions,
        "source": _source_binding(
            snapshot,
            (
                "krx/acquisition-receipt.json",
                "krx/landing.html",
                "krx/market-closing-2026.json",
            ),
            krx_receipt,
        ),
        "limitations": _KRX_LIMITATIONS,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    arcx = {
        "type": "arcx_koru_core_session_calendar_v1",
        "schema_version": 1,
        "venue": "ARCX",
        "instrument": "KORU",
        "session_kind": "core",
        "coverage": coverage,
        "source_timezone": "America/New_York",
        "source_utc_offset_for_coverage": "-04:00",
        "source_dst_state_for_coverage": "EDT",
        "source_local_core_hours": {"open": "09:30:00", "close": "16:00:00"},
        "source_closures_2026": [
            {"date": day, "reason": reason} for day, reason in nyse_closures
        ],
        "applied_closure_dates": ["2026-09-07"],
        "source_early_close_dates_2026": ["2026-11-27", "2026-12-24"],
        "early_close_dates_in_coverage": [],
        "sessions": arcx_sessions,
        "source": _source_binding(
            snapshot,
            ("nyse/acquisition-receipt.json", "nyse/hours-calendars.html"),
            nyse_receipt,
        ),
        "limitations": _ARCX_LIMITATIONS,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    return xkrx, arcx


def _unit_payload(
    snapshot: SourceSnapshot,
    adjustment: dict[str, Any],
    completion: dict[str, Any],
    receipt: dict[str, Any],
) -> dict[str, object]:
    return {
        "type": "binance_usdm_tradifi_post_adjustment_unit_regime_v1",
        "schema_version": 1,
        "venue": "BINANCE_USDM",
        "instrument": "KORUUSDT",
        "coverage": {
            "start": _COVERAGE_START,
            "end_exclusive": _COVERAGE_END_EXCLUSIVE,
        },
        "adjustment": {
            "starts_at": "2026-07-15T00:15:00Z",
            "scale_factor": 20,
            "share_split_relationship": "20-for-1",
            "price_relationship": "post_adjustment_price=pre_adjustment_price/20",
            "quantity_relationship": "post_adjustment_quantity=pre_adjustment_quantity*20",
            "source_examples": {
                "price": "800/20=40",
                "quantity": "20*20=400",
            },
        },
        "market_session_states": [
            {
                "state": "trading_halt",
                "start": "2026-07-15T00:15:00Z",
                "end_exclusive": "2026-07-15T09:30:00Z",
            },
            {
                "state": "cancel_only",
                "start": "2026-07-15T09:30:00Z",
                "end_exclusive": "2026-07-15T09:35:00Z",
            },
            {
                "state": "continuous_trading",
                "start": "2026-07-15T09:35:00Z",
                "end_exclusive": None,
            },
        ],
        "authoritative_post_adjustment_admission": {
            "start": _COVERAGE_START,
            "end_exclusive": _COVERAGE_END_EXCLUSIVE,
            "pre_adjustment_admission": False,
            "cross_regime_admission": False,
        },
        "source_articles": [
            {
                "role": "announced_adjustment",
                "article_code": adjustment["code"],
                "article_id": adjustment["id"],
                "publish_date_epoch_milliseconds": adjustment["publishDate"],
                "member_hash": _MEMBER_HASHES["binance/adjustment-announcement.json"],
                "body_sha256": _digest(cast(str, adjustment["body"]).encode("utf-8")),
            },
            {
                "role": "completed_adjustment",
                "article_code": completion["code"],
                "article_id": completion["id"],
                "publish_date_epoch_milliseconds": completion["publishDate"],
                "member_hash": _MEMBER_HASHES["binance/completion-announcement.json"],
                "body_sha256": _digest(cast(str, completion["body"]).encode("utf-8")),
            },
        ],
        "source": _source_binding(
            snapshot,
            (
                "binance/acquisition-receipt.json",
                "binance/adjustment-announcement.json",
                "binance/completion-announcement.json",
            ),
            receipt,
        ),
        "limitations": _UNIT_LIMITATIONS,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }


def _expected_hashes(value: object) -> tuple[tuple[str, str], ...]:
    if type(value) is not tuple:
        raise TypeError("expected_hashes must be exact tuple")
    result = cast(tuple[object, ...], value)
    if any(
        type(item) is not tuple
        or len(cast(tuple[object, ...], item)) != 2
        or type(cast(tuple[object, ...], item)[0]) is not str
        or type(cast(tuple[object, ...], item)[1]) is not str
        for item in result
    ):
        raise TypeError("expected_hashes entries must be exact string pairs")
    pairs = cast(tuple[tuple[str, str], ...], result)
    if pairs != APPROVED_MEMBER_HASHES or any(
        _HASH.fullmatch(value) is None for _, value in pairs
    ):
        raise ValueError("expected_hashes do not match approved fixture authority")
    return pairs


def build_koru_tradifi_calendar_unit_authority_v1(
    *,
    members: tuple[RawSourceMember, ...],
    expected_hashes: tuple[tuple[str, str], ...],
) -> KoruTradifiCalendarUnitAuthorityOutcomeV1:
    try:
        _expected_hashes(expected_hashes)
        if type(members) is not tuple or any(
            type(value) is not RawSourceMember for value in members
        ):
            raise TypeError("members must be exact tuple of RawSourceMember")
        if tuple(sorted(value.member_key for value in members)) != tuple(
            _MEMBER_HASHES
        ):
            raise ValueError("authority member set mismatch")
        if any(
            value.mode != "0644"
            or value.declared_sha256 != _MEMBER_HASHES[value.member_key]
            or value.raw_bytes is None
            or _digest(value.raw_bytes) != _MEMBER_HASHES[value.member_key]
            for value in members
        ):
            raise ValueError("authority member hash mismatch")
        frozen = freeze_source_snapshot(members=members, provenance=_PROVENANCE)
        if frozen.snapshot is None:
            return _failed(
                KoruTradifiCalendarUnitAuthorityFailureCode.SOURCE_SNAPSHOT_INVALID
            )
        snapshot = frozen.snapshot
        raw = _member_map(snapshot)
        krx_closures, krx_receipt = _parse_krx(raw, snapshot)
        nyse_closures, nyse_receipt = _parse_nyse(raw, snapshot)
        adjustment, completion, binance_receipt = _parse_binance(raw, snapshot)
        xkrx_payload, arcx_payload = _calendar_payloads(
            snapshot,
            krx_closures,
            krx_receipt,
            nyse_closures,
            nyse_receipt,
        )
        xkrx = ArtifactEnvelope.create(_KRX_ARTIFACT, 1, xkrx_payload)
        arcx = ArtifactEnvelope.create(_ARCX_ARTIFACT, 1, arcx_payload)
        unit = ArtifactEnvelope.create(
            _UNIT_ARTIFACT,
            1,
            _unit_payload(snapshot, adjustment, completion, binance_receipt),
        )
        result = KoruTradifiCalendarUnitAuthorityResultV1(
            source_snapshot=snapshot,
            xkrx_calendar=xkrx,
            arcx_calendar=arcx,
            post_adjustment_unit_regime=unit,
            xkrx_calendar_ref=ArtifactRef.from_envelope(xkrx),
            arcx_calendar_ref=ArtifactRef.from_envelope(arcx),
            post_adjustment_unit_regime_ref=ArtifactRef.from_envelope(unit),
        )
        return KoruTradifiCalendarUnitAuthorityOutcomeV1(result, None)
    except (KeyError, TypeError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
        return _failed(
            KoruTradifiCalendarUnitAuthorityFailureCode.SOURCE_ATTESTATION_MISMATCH
        )


def verify_koru_tradifi_calendar_unit_authority_v1(
    *,
    result: KoruTradifiCalendarUnitAuthorityResultV1,
    expected_hashes: tuple[tuple[str, str], ...],
) -> KoruTradifiCalendarUnitAuthorityOutcomeV1:
    try:
        _expected_hashes(expected_hashes)
        if type(result) is not KoruTradifiCalendarUnitAuthorityResultV1:
            raise TypeError("result must be exact authority result")
        verified = verify_source_snapshot(result.source_snapshot)
        if verified.snapshot is None:
            return _failed(
                KoruTradifiCalendarUnitAuthorityFailureCode.SOURCE_SNAPSHOT_INVALID
            )
        members = tuple(
            RawSourceMember(
                member_key=member.member_key,
                raw_bytes=result.source_snapshot.member_bytes(member.member_key),
                mode=member.mode,
                acquired_at_epoch_nanoseconds=member.acquired_at_epoch_nanoseconds,
                declared_sha256=member.declared_sha256,
            )
            for member in result.source_snapshot.members
        )
        replay = build_koru_tradifi_calendar_unit_authority_v1(
            members=members, expected_hashes=expected_hashes
        )
        if replay.result is None:
            return cast(KoruTradifiCalendarUnitAuthorityOutcomeV1, replay)
        if canonical_bytes(replay.result) != canonical_bytes(result):
            return _failed(KoruTradifiCalendarUnitAuthorityFailureCode.RESULT_MISMATCH)
        return KoruTradifiCalendarUnitAuthorityOutcomeV1(result, None)
    except (KeyError, TypeError, ValueError):
        return _failed(KoruTradifiCalendarUnitAuthorityFailureCode.RESULT_MISMATCH)
