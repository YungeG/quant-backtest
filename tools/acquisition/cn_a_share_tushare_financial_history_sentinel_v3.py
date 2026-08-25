from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, cast

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotFailureCode,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)

from ._common import AcquisitionError, json_bytes, sha256
from .cn_a_share_tushare import _source_bounded_rows_v2
from .cn_a_share_tushare_financial_sentinel_v1 import (
    _provider_response,
    _require_safe_output,
)
from .cn_a_share_tushare_financial_sentinel_v2 import (
    _BALANCE_FIELDS,
    _CASHFLOW_FIELDS,
    _INCOME_FIELDS,
)
from .cn_a_share_tushare_listing_source_bounded_v2 import (
    ProxyPost,
    _ALLOWED_ENDPOINTS as _PROXY_ENDPOINTS,
    _PROXY_KEY,
    _headers as _proxy_headers,
    _post_with_retries as _proxy_post_with_retries,
    _request_body as _proxy_request_body,
    _stdlib_post as _proxy_stdlib_post,
)

CninfoPost = Callable[
    [str, tuple[tuple[str, str], ...], dict[str, str]],
    tuple[int, bytes],
]
Get = Callable[[str], tuple[int, bytes, str]]


class FinancialHistorySentinelV3FailureCode(str, Enum):
    INPUT_MISMATCH = "INPUT_MISMATCH"
    CREDENTIAL_INPUT_INVALID = "CREDENTIAL_INPUT_INVALID"
    OUTPUT_PATH_INVALID = "OUTPUT_PATH_INVALID"
    PROVIDER_TRANSPORT_FAILURE = "PROVIDER_TRANSPORT_FAILURE"
    PROVIDER_RESPONSE_INVALID = "PROVIDER_RESPONSE_INVALID"
    PROVIDER_FIELDS_MISMATCH = "PROVIDER_FIELDS_MISMATCH"
    FINANCIAL_ROW_SCOPE_MISMATCH = "FINANCIAL_ROW_SCOPE_MISMATCH"
    CREDENTIAL_LEAK_DETECTED = "CREDENTIAL_LEAK_DETECTED"
    OFFICIAL_METADATA_TRANSPORT_FAILURE = "OFFICIAL_METADATA_TRANSPORT_FAILURE"
    OFFICIAL_METADATA_INVALID = "OFFICIAL_METADATA_INVALID"
    OFFICIAL_DOCUMENT_TRANSPORT_FAILURE = "OFFICIAL_DOCUMENT_TRANSPORT_FAILURE"
    ANNUAL_REPORT_MISMATCH = "ANNUAL_REPORT_MISMATCH"
    PUBLICATION_FAILURE = "PUBLICATION_FAILURE"


class FinancialHistorySentinelV3AcquisitionError(AcquisitionError):
    code: FinancialHistorySentinelV3FailureCode | SourceSnapshotFailureCode

    def __init__(
        self,
        code: FinancialHistorySentinelV3FailureCode | SourceSnapshotFailureCode,
    ) -> None:
        if type(code) not in (
            FinancialHistorySentinelV3FailureCode,
            SourceSnapshotFailureCode,
        ):
            raise TypeError("code must be an exact financial-history or snapshot enum")
        self.code = code
        super().__init__(code.value)


_TS_CODE = "000651.SZ"
_INSTRUMENT = "xshe:000651"
_ISSUER = "珠海格力电器股份有限公司"
_COMP_TYPE = "1"
_PREDECESSOR = "5338d8046fa0f304d4a9590989c59ceffb51270b"
_EXISTING_2023_SNAPSHOT = (
    "sha256:dec0abb1828f8b87256347e72b6ccfe2f84a2ca13f36aa1415c9a53e96a0c7d5"
)
_PROBE_MANIFEST_SHA256 = (
    "sha256:2240d65b0533f5cb0898d406d2113df3ea48e31b6cda3e500eba25ee2de2d1a0"
)
_PURPOSE_SCOPE = "cn-a-share.financial-history-source-sentinel.000651.sz.2018-2022.v3"
_CNINFO_ENDPOINT = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
_CNINFO_MEMBER = (
    "response/cninfo/announcement-query/000651.SZ-2019-2023-annual-reports-v3.json"
)
_CNINFO_FORM = (
    ("pageNum", "1"),
    ("pageSize", "30"),
    ("column", "szse"),
    ("tabName", "fulltext"),
    ("plate", "sz"),
    ("stock", "000651,gssz0000651"),
    ("searchkey", ""),
    ("secid", ""),
    ("category", "category_ndbg_szsh"),
    ("trade", ""),
    ("seDate", "2019-01-01~2023-12-31"),
    ("sortName", ""),
    ("sortType", ""),
    ("isHLtitle", "true"),
)
_CNINFO_HEADERS = (
    ("Accept", "application/json, text/javascript, */*; q=0.01"),
    ("Content-Type", "application/x-www-form-urlencoded; charset=UTF-8"),
    ("Referer", "https://www.cninfo.com.cn/"),
    ("User-Agent", "Mozilla/5.0"),
    ("X-Requested-With", "XMLHttpRequest"),
)
_ANNUAL_REPORT_FACTS = (
    (
        "20181231",
        "1206125365",
        "https://static.cninfo.com.cn/finalpage/2019-04-29/1206125365.PDF",
        "response/cninfo/annual-report/1206125365.pdf",
        6_718_851,
        "sha256:b147eb6b8a4aaf093f3b83550c70e8526415b5b54fe24e4258ce7bfd11d5406a",
    ),
    (
        "20191231",
        "1207685438",
        "https://static.cninfo.com.cn/finalpage/2020-04-30/1207685438.PDF",
        "response/cninfo/annual-report/1207685438.pdf",
        7_535_725,
        "sha256:1b4869caab122969b322738df69955d788c8dc19b4c6d57188619177e922e708",
    ),
    (
        "20201231",
        "1209855305",
        "https://static.cninfo.com.cn/finalpage/2021-04-29/1209855305.PDF",
        "response/cninfo/annual-report/1209855305.pdf",
        3_444_361,
        "sha256:0d3c39090adf97fede39149a731a5636bd0eca2002606fb942ca70121dba9072",
    ),
    (
        "20211231",
        "1213262535",
        "https://static.cninfo.com.cn/finalpage/2022-04-30/1213262535.PDF",
        "response/cninfo/annual-report/1213262535.pdf",
        4_110_139,
        "sha256:96065ec44285bce7a9c0cbee25dfeb2368ec4552d72f06ebf3ecab35136e2444",
    ),
    (
        "20221231",
        "1216702261",
        "https://static.cninfo.com.cn/finalpage/2023-04-29/1216702261.PDF",
        "response/cninfo/annual-report/1216702261.pdf",
        3_765_397,
        "sha256:7cfc80c2badbf4cd74c5adc080d5072b02cd6c700b04fa7ca0ac44cb8b8fe987",
    ),
)
_METADATA_FACTS = (
    ("20181231", "1206125365", 1_556_467_200_000, "finalpage/2019-04-29/1206125365.PDF"),
    ("20191231", "1207685438", 1_588_176_000_000, "finalpage/2020-04-30/1207685438.PDF"),
    ("20201231", "1209855305", 1_619_625_600_000, "finalpage/2021-04-29/1209855305.PDF"),
    ("20211231", "1213262535", 1_651_248_000_000, "finalpage/2022-04-30/1213262535.PDF"),
    ("20221231", "1216702261", 1_682_697_600_000, "finalpage/2023-04-29/1216702261.PDF"),
)
_PERIODS = tuple(fact[0] for fact in _ANNUAL_REPORT_FACTS)
_REQUESTS = (
    ("balancesheet", "20181231", "20190429", _BALANCE_FIELDS, 2, ("0", "1")),
    ("income", "20191231", "20200430", _INCOME_FIELDS, 2, ("0", "1")),
    ("balancesheet", "20191231", "20200430", _BALANCE_FIELDS, 2, ("0", "1")),
    ("cashflow", "20191231", "20200430", _CASHFLOW_FIELDS, 2, ("0", "1")),
    ("income", "20201231", "20210429", _INCOME_FIELDS, 2, ("0", "1")),
    ("balancesheet", "20201231", "20210429", _BALANCE_FIELDS, 2, ("0", "1")),
    ("cashflow", "20201231", "20210429", _CASHFLOW_FIELDS, 2, ("0", "1")),
    ("income", "20211231", "20220430", _INCOME_FIELDS, 2, ("0", "1")),
    ("balancesheet", "20211231", "20220430", _BALANCE_FIELDS, 2, ("0", "1")),
    ("cashflow", "20211231", "20220430", _CASHFLOW_FIELDS, 2, ("0", "1")),
    ("income", "20221231", "20230429", _INCOME_FIELDS, 1, ("1",)),
    ("balancesheet", "20221231", "20230429", _BALANCE_FIELDS, 2, ("0", "1")),
    ("cashflow", "20221231", "20230429", _CASHFLOW_FIELDS, 2, ("0", "1")),
)
_LIMITATIONS = (
    "source-bounded finite capture only",
    "existing 2023 SourceSnapshot is separate and unmodified",
    "CNINFO metadata timestamp is date-only authority",
    "no accepted Trading Calendar or available_at result",
    "no official statement-unit, debt, D&A or revision-closure declarations",
    "provider update_flag does not prove finality or supersession",
    "no normalized revisions, selected trios, formulas or five-year feature manifest",
    "no full-market, audit-opinion, penalty, pledge, Universe or corporate-action coverage",
    "no decision-grade, Validation, Live or deployment authority",
)
_METADATA_KEYS = {
    "announcements",
    "categoryList",
    "classifiedAnnouncements",
    "hasMore",
    "totalAnnouncement",
    "totalRecordNum",
    "totalSecurities",
    "totalpages",
}
_ANNOUNCEMENT_KEYS = {
    "id",
    "secCode",
    "secName",
    "orgId",
    "announcementId",
    "announcementTitle",
    "announcementTime",
    "adjunctUrl",
    "adjunctSize",
    "adjunctType",
    "storageTime",
    "columnId",
    "pageColumn",
    "announcementType",
    "associateAnnouncement",
    "important",
    "batchNum",
    "announcementContent",
    "orgName",
    "tileSecName",
    "shortTitle",
    "announcementTypeName",
    "secNameList",
}


def _annual_report_request_facts() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "period": period,
            "announcement_id": announcement_id,
            "url": url,
            "member_key": member_key,
            "byte_count": byte_count,
            "sha256": expected_sha256,
        }
        for period, announcement_id, url, member_key, byte_count, expected_sha256 in _ANNUAL_REPORT_FACTS
    )


@dataclass(frozen=True, slots=True)
class TushareCnAShareFinancialHistorySentinelRequestV3:
    schema_version: int = 3

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 3:
            raise ValueError("request must be the exact frozen financial history sentinel v3 scope")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_financial_history_sentinel_request",
            "schema_version": 3,
            "predecessor_commit": _PREDECESSOR,
            "issuer": _ISSUER,
            "provider_security_code": _TS_CODE,
            "instrument_candidate": _INSTRUMENT,
            "company_type": _COMP_TYPE,
            "historical_periods": _PERIODS,
            "existing_2023_source_snapshot_id": _EXISTING_2023_SNAPSHOT,
            "probe_manifest_file_sha256": _PROBE_MANIFEST_SHA256,
            "cninfo_metadata_endpoint": _CNINFO_ENDPOINT,
            "cninfo_metadata_form": _CNINFO_FORM,
            "annual_reports": _annual_report_request_facts(),
            "purpose_scope": _PURPOSE_SCOPE,
        }


def _map_provider_failure(code: object) -> FinancialHistorySentinelV3FailureCode:
    try:
        return FinancialHistorySentinelV3FailureCode(str(getattr(code, "value")))
    except ValueError:
        return FinancialHistorySentinelV3FailureCode.PROVIDER_RESPONSE_INVALID


def _member_key(api_name: str, period: str, ann_date: str) -> str:
    return f"response/tushare/{api_name}/{_TS_CODE}-{period}-{ann_date}-v3.json"


def _valid_timestamp(value: object) -> bool:
    return type(value) is int and cast(int, value) >= 0


def _timestamp(
    time_ns: Callable[[], int], code: FinancialHistorySentinelV3FailureCode
) -> int:
    try:
        value = time_ns()
    except Exception:  # noqa: BLE001 -- collaborator details are credential-adjacent.
        raise FinancialHistorySentinelV3AcquisitionError(code) from None
    if not _valid_timestamp(value):
        raise FinancialHistorySentinelV3AcquisitionError(code)
    return value


def _validate_provider_rows(
    rows: list[list[object]],
    *,
    fields: tuple[str, ...],
    period: str,
    ann_date: str,
    expected_count: int,
    expected_flags: tuple[str, ...],
) -> tuple[list[list[str]], list[str]]:
    positions = {field: index for index, field in enumerate(fields)}
    contexts: list[list[str]] = []
    serialized: list[bytes] = []
    for row in rows:
        if type(row) is not list or len(row) != len(fields):
            raise FinancialHistorySentinelV3AcquisitionError(
                FinancialHistorySentinelV3FailureCode.FINANCIAL_ROW_SCOPE_MISMATCH
            )
        context_names = (
            "ts_code",
            "ann_date",
            "f_ann_date",
            "end_date",
            "report_type",
            "comp_type",
            "update_flag",
        )
        if any(type(row[positions[name]]) is not str for name in context_names):
            raise FinancialHistorySentinelV3AcquisitionError(
                FinancialHistorySentinelV3FailureCode.FINANCIAL_ROW_SCOPE_MISMATCH
            )
        context = {name: cast(str, row[positions[name]]) for name in context_names}
        if context != {
            "ts_code": _TS_CODE,
            "ann_date": ann_date,
            "f_ann_date": ann_date,
            "end_date": period,
            "report_type": "1",
            "comp_type": _COMP_TYPE,
            "update_flag": context["update_flag"],
        }:
            raise FinancialHistorySentinelV3AcquisitionError(
                FinancialHistorySentinelV3FailureCode.FINANCIAL_ROW_SCOPE_MISMATCH
            )
        if any(
            value is not None
            and type(value) is not int
            and not (type(value) is float and math.isfinite(value))
            for index, value in enumerate(row)
            if index not in {positions[name] for name in context_names}
        ):
            raise FinancialHistorySentinelV3AcquisitionError(
                FinancialHistorySentinelV3FailureCode.FINANCIAL_ROW_SCOPE_MISMATCH
            )
        contexts.append([context[name] for name in context_names])
        serialized.append(
            json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode()
        )
    update_flags = [context[-1] for context in contexts]
    if (
        len(rows) != expected_count
        or tuple(sorted(update_flags)) != expected_flags
        or len(serialized) != len(set(serialized))
    ):
        raise FinancialHistorySentinelV3AcquisitionError(
            FinancialHistorySentinelV3FailureCode.FINANCIAL_ROW_SCOPE_MISMATCH
        )
    return contexts, update_flags


def _unique_json(source_bytes: bytes, code: FinancialHistorySentinelV3FailureCode) -> object:
    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise ValueError(value)

    try:
        return json.loads(
            source_bytes,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
        raise FinancialHistorySentinelV3AcquisitionError(code) from None


def _contains_text(value: object, text: str) -> bool:
    pending = [value]
    while pending:
        item = pending.pop()
        if type(item) is str and text in item:
            return True
        if type(item) is dict:
            pending.extend(item.keys())
            pending.extend(item.values())
        elif type(item) is list:
            pending.extend(item)
    return False


def _normalize_title(title: str) -> str:
    result: list[str] = []
    depth = 0
    position = 0
    while position < len(title):
        if title.startswith("<em>", position):
            depth += 1
            position += 4
        elif title.startswith("</em>", position):
            if depth == 0:
                raise ValueError("unbalanced highlight")
            depth -= 1
            position += 5
        else:
            result.append(title[position])
            position += 1
    normalized = "".join(result)
    if depth != 0 or "<" in normalized or ">" in normalized:
        raise ValueError("invalid title markup")
    return normalized


def _validate_metadata(
    source_bytes: bytes, forbidden_text: str
) -> tuple[dict[str, int | bool], list[dict[str, object]]]:
    payload = _unique_json(
        source_bytes, FinancialHistorySentinelV3FailureCode.OFFICIAL_METADATA_INVALID
    )
    invalid = FinancialHistorySentinelV3AcquisitionError(
        FinancialHistorySentinelV3FailureCode.OFFICIAL_METADATA_INVALID
    )
    if type(payload) is not dict or set(payload) != _METADATA_KEYS:
        raise invalid
    announcements = payload["announcements"]
    totals = (
        payload["totalAnnouncement"],
        payload["totalRecordNum"],
        payload["totalSecurities"],
        payload["totalpages"],
    )
    if (
        type(announcements) is not list
        or payload["categoryList"] is not None
        or payload["classifiedAnnouncements"] is not None
        or payload["hasMore"] is not False
        or any(type(value) is not int for value in totals)
        or totals[0] != totals[1]
        or totals[0] != len(announcements)
        or totals[2] != 0
        or totals[3] < 0
    ):
        raise invalid
    normalized_records: list[tuple[dict[str, object], str]] = []
    core_strings = {
        "secCode",
        "secName",
        "orgId",
        "announcementId",
        "announcementTitle",
        "adjunctUrl",
        "adjunctType",
    }
    for record in announcements:
        if (
            type(record) is not dict
            or set(record) != _ANNOUNCEMENT_KEYS
            or any(type(record[name]) is not str for name in core_strings)
            or type(record["announcementTime"]) is not int
            or type(record["adjunctSize"]) is not int
            or any(
                type(value) not in (type(None), str, list, int)
                for name, value in record.items()
                if name not in core_strings
            )
        ):
            raise invalid
        try:
            normalized = _normalize_title(cast(str, record["announcementTitle"]))
        except ValueError:
            raise invalid from None
        normalized_records.append((record, normalized))

    selected: list[dict[str, object]] = []
    for period, announcement_id, announcement_time, adjunct_url in _METADATA_FACTS:
        title = f"{period[:4]}年年度报告"
        matches = [
            (record, normalized)
            for record, normalized in normalized_records
            if normalized == title
            and record["secCode"] == "000651"
            and record["orgId"] == "gssz0000651"
            and record["adjunctType"] == "PDF"
            and record["announcementId"] == announcement_id
            and record["announcementTime"] == announcement_time
            and record["adjunctUrl"] == adjunct_url
        ]
        if len(matches) != 1:
            raise invalid
        record, normalized = matches[0]
        selected.append(
            {
                "report_period": period,
                "sec_code": record["secCode"],
                "org_id": record["orgId"],
                "announcement_id": record["announcementId"],
                "raw_announcement_title": record["announcementTitle"],
                "normalized_announcement_title": normalized,
                "announcement_time_epoch_milliseconds": record["announcementTime"],
                "adjunct_url": record["adjunctUrl"],
                "adjunct_type": record["adjunctType"],
            }
        )
    if _contains_text(payload, forbidden_text):
        raise FinancialHistorySentinelV3AcquisitionError(
            FinancialHistorySentinelV3FailureCode.CREDENTIAL_LEAK_DETECTED
        )
    return (
        {
            "has_more": False,
            "total_announcement": cast(int, totals[0]),
            "total_record_num": cast(int, totals[1]),
            "total_securities": cast(int, totals[2]),
            "total_pages": cast(int, totals[3]),
        },
        selected,
    )


def _cninfo_post_with_retries(
    cninfo_post: CninfoPost,
    sleep: Callable[[float], None],
    headers: dict[str, str],
) -> tuple[bytes, int]:
    for attempt in range(1, 4):
        try:
            response = cninfo_post(_CNINFO_ENDPOINT, _CNINFO_FORM, headers)
        except Exception:  # noqa: BLE001 -- redact callback/transport details.
            response = None
        if response is not None:
            if (
                type(response) is not tuple
                or len(response) != 2
                or type(response[0]) is not int
                or type(response[1]) is not bytes
            ):
                raise FinancialHistorySentinelV3AcquisitionError(
                    FinancialHistorySentinelV3FailureCode.OFFICIAL_METADATA_TRANSPORT_FAILURE
                )
            status, body = response
            if status == 200:
                return body, attempt
            if status not in {429, 500, 502, 503, 504}:
                raise FinancialHistorySentinelV3AcquisitionError(
                    FinancialHistorySentinelV3FailureCode.OFFICIAL_METADATA_TRANSPORT_FAILURE
                )
        if attempt == 3:
            break
        try:
            sleep((0.5, 1.0)[attempt - 1])
        except Exception:  # noqa: BLE001 -- redact collaborator details.
            raise FinancialHistorySentinelV3AcquisitionError(
                FinancialHistorySentinelV3FailureCode.OFFICIAL_METADATA_TRANSPORT_FAILURE
            ) from None
    raise FinancialHistorySentinelV3AcquisitionError(
        FinancialHistorySentinelV3FailureCode.OFFICIAL_METADATA_TRANSPORT_FAILURE
    )


def _get_with_retries(
    url: str,
    get: Get,
    sleep: Callable[[float], None],
) -> tuple[bytes, int, str]:
    for attempt in range(1, 4):
        try:
            response = get(url)
        except Exception:  # noqa: BLE001 -- redact callback/transport details.
            response = None
        if response is not None:
            if (
                type(response) is not tuple
                or len(response) != 3
                or type(response[0]) is not int
                or type(response[1]) is not bytes
                or type(response[2]) is not str
            ):
                raise FinancialHistorySentinelV3AcquisitionError(
                    FinancialHistorySentinelV3FailureCode.OFFICIAL_DOCUMENT_TRANSPORT_FAILURE
                )
            status, body, final_url = response
            if status == 200:
                if final_url != url:
                    raise FinancialHistorySentinelV3AcquisitionError(
                        FinancialHistorySentinelV3FailureCode.OFFICIAL_DOCUMENT_TRANSPORT_FAILURE
                    )
                return body, attempt, final_url
            if status not in {429, 500, 502, 503, 504}:
                raise FinancialHistorySentinelV3AcquisitionError(
                    FinancialHistorySentinelV3FailureCode.OFFICIAL_DOCUMENT_TRANSPORT_FAILURE
                )
        if attempt == 3:
            break
        try:
            sleep((0.5, 1.0)[attempt - 1])
        except Exception:  # noqa: BLE001 -- redact collaborator details.
            raise FinancialHistorySentinelV3AcquisitionError(
                FinancialHistorySentinelV3FailureCode.OFFICIAL_DOCUMENT_TRANSPORT_FAILURE
            ) from None
    raise FinancialHistorySentinelV3AcquisitionError(
        FinancialHistorySentinelV3FailureCode.OFFICIAL_DOCUMENT_TRANSPORT_FAILURE
    )


def _provenance() -> SourceSnapshotProvenance:
    return SourceSnapshotProvenance(
        vendor_key="tushare.pro-via-xiaodefa-cninfo.com.cn",
        source_key="cn_a_share.financial_history_source_sentinel.000651.sz.2018-2022.v3.proxy",
        license_ref="tushare.pro.terms-cninfo.public-disclosure",
        retention_policy_ref="backtest.acquisition.candidate",
    )


def _raw_members(
    files: dict[str, bytes], received_at: dict[str, int]
) -> tuple[RawSourceMember, ...]:
    declared = {fact[3]: fact[5] for fact in _ANNUAL_REPORT_FACTS}
    return tuple(
        RawSourceMember(
            member_key,
            source_bytes,
            "0644",
            received_at[member_key],
            declared.get(member_key),
        )
        for member_key, source_bytes in files.items()
    )


def _freeze(files: dict[str, bytes], received_at: dict[str, int]):
    outcome = freeze_source_snapshot(
        members=_raw_members(files, received_at), provenance=_provenance()
    )
    if outcome.snapshot is None:
        code = (
            outcome.failure.code
            if outcome.failure is not None
            else SourceSnapshotFailureCode.ACQUISITION_FAILED
        )
        raise FinancialHistorySentinelV3AcquisitionError(code)
    verification = verify_source_snapshot(outcome.snapshot)
    if verification.failure is not None:
        raise FinancialHistorySentinelV3AcquisitionError(verification.failure.code)
    return outcome.snapshot


def _preflight_output(final_dir: Path) -> Path:
    staging_dir = final_dir.parent / f".{final_dir.name}.staging-v3"
    try:
        _require_safe_output(final_dir)
        _require_safe_output(staging_dir)
    except (AcquisitionError, OSError, ValueError):
        raise FinancialHistorySentinelV3AcquisitionError(
            FinancialHistorySentinelV3FailureCode.OUTPUT_PATH_INVALID
        ) from None
    return staging_dir


def _publish(
    final_dir: Path,
    staging_dir: Path,
    files: dict[str, bytes],
    received_at: dict[str, int],
    receipt: dict[str, object],
    snapshot_dict: dict[str, object],
) -> None:
    published = (*files.items(), ("acquisition-receipt.json", json_bytes(receipt)))
    try:
        staging_dir.mkdir(mode=0o700)
    except Exception as error:  # noqa: BLE001 -- publication errors expose only the code.
        code = (
            FinancialHistorySentinelV3FailureCode.OUTPUT_PATH_INVALID
            if isinstance(error, FileExistsError)
            else FinancialHistorySentinelV3FailureCode.PUBLICATION_FAILURE
        )
        raise FinancialHistorySentinelV3AcquisitionError(code) from None
    try:
        for relative, source_bytes in published:
            path = staging_dir / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                os.fchmod(descriptor, 0o600)
                with os.fdopen(descriptor, "wb") as handle:
                    descriptor = -1
                    handle.write(source_bytes)
                    handle.flush()
                    os.fsync(handle.fileno())
            finally:
                if descriptor >= 0:
                    os.close(descriptor)
        for relative, source_bytes in published:
            persisted = (staging_dir / relative).read_bytes()
            if persisted != source_bytes or sha256(persisted) != sha256(source_bytes):
                raise OSError("staged readback mismatch")
        staged_files = {key: (staging_dir / key).read_bytes() for key in files}
        staged_snapshot = _freeze(staged_files, received_at)
        if staged_snapshot.to_canonical_dict() != snapshot_dict:
            raise OSError("staged snapshot mismatch")
        directory = os.open(staging_dir, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        try:
            _require_safe_output(final_dir)
        except (AcquisitionError, OSError, ValueError):
            raise FinancialHistorySentinelV3AcquisitionError(
                FinancialHistorySentinelV3FailureCode.OUTPUT_PATH_INVALID
            ) from None
        os.rename(staging_dir, final_dir)
        return
    except BaseException as error:  # publication cleanup must include interruption.
        shutil.rmtree(staging_dir, ignore_errors=True)
        if (
            isinstance(error, FinancialHistorySentinelV3AcquisitionError)
            and error.code is FinancialHistorySentinelV3FailureCode.OUTPUT_PATH_INVALID
        ):
            raise
        raise FinancialHistorySentinelV3AcquisitionError(
            FinancialHistorySentinelV3FailureCode.PUBLICATION_FAILURE
        ) from None


def acquire_tushare_cn_a_share_financial_history_sentinel_v3(
    request: TushareCnAShareFinancialHistorySentinelRequestV3,
    *,
    token: str,
    endpoint: str,
    output_dir: str | Path,
    proxy_post: ProxyPost,
    cninfo_post: CninfoPost,
    get: Get,
    time_ns: Callable[[], int] = time.time_ns,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    if (
        type(request) is not TushareCnAShareFinancialHistorySentinelRequestV3
        or request != TushareCnAShareFinancialHistorySentinelRequestV3()
        or type(endpoint) is not str
        or endpoint not in _PROXY_ENDPOINTS
        or not isinstance(output_dir, (str, Path))
        or not callable(proxy_post)
        or not callable(cninfo_post)
        or not callable(get)
        or not callable(time_ns)
        or not callable(sleep)
    ):
        raise FinancialHistorySentinelV3AcquisitionError(
            FinancialHistorySentinelV3FailureCode.INPUT_MISMATCH
        )
    if (
        type(token) is not str
        or len(token) != 56
        or token != token.strip()
        or any(character.isspace() for character in token)
    ):
        raise FinancialHistorySentinelV3AcquisitionError(
            FinancialHistorySentinelV3FailureCode.CREDENTIAL_INPUT_INVALID
        )
    token_bytes = token.encode()
    if token_bytes in json_bytes(request.to_canonical_dict()) or token in os.fspath(output_dir):
        raise FinancialHistorySentinelV3AcquisitionError(
            FinancialHistorySentinelV3FailureCode.CREDENTIAL_INPUT_INVALID
        )
    final_dir = Path(output_dir)
    staging_dir = _preflight_output(final_dir)

    files: dict[str, bytes] = {}
    received_at: dict[str, int] = {}
    provider_requests: list[dict[str, object]] = []
    for position, (
        api_name,
        period,
        ann_date,
        fields,
        expected_count,
        expected_flags,
    ) in enumerate(_REQUESTS):
        if position:
            try:
                sleep(0.5)
            except Exception:  # noqa: BLE001 -- redact collaborator details.
                raise FinancialHistorySentinelV3AcquisitionError(
                    FinancialHistorySentinelV3FailureCode.PROVIDER_TRANSPORT_FAILURE
                ) from None
        params: dict[str, object] = {
            "ts_code": _TS_CODE,
            "comp_type": _COMP_TYPE,
            "period": period,
            "ann_date": ann_date,
        }
        body = _proxy_request_body(api_name, params, fields)
        request_headers = _proxy_headers(token)
        try:
            source_bytes, attempts = _proxy_post_with_retries(
                api_name,
                endpoint=endpoint,
                body=body,
                headers=request_headers,
                post=proxy_post,
                sleep=sleep,
            )
        except Exception:  # noqa: BLE001 -- redact proxy/callback details.
            raise FinancialHistorySentinelV3AcquisitionError(
                FinancialHistorySentinelV3FailureCode.PROVIDER_TRANSPORT_FAILURE
            ) from None
        expected_body = _proxy_request_body(
            api_name,
            {
                "ts_code": _TS_CODE,
                "comp_type": _COMP_TYPE,
                "period": period,
                "ann_date": ann_date,
            },
            fields,
        )
        if body != expected_body or request_headers != _proxy_headers(token):
            raise FinancialHistorySentinelV3AcquisitionError(
                FinancialHistorySentinelV3FailureCode.PROVIDER_TRANSPORT_FAILURE
            )
        try:
            failure, rows, has_more, count = _provider_response(source_bytes, fields)
        except RecursionError:
            raise FinancialHistorySentinelV3AcquisitionError(
                FinancialHistorySentinelV3FailureCode.PROVIDER_RESPONSE_INVALID
            ) from None
        if failure is not None:
            raise FinancialHistorySentinelV3AcquisitionError(
                _map_provider_failure(failure)
            )
        if has_more is not False or type(count) is not int or count != 0:
            raise FinancialHistorySentinelV3AcquisitionError(
                FinancialHistorySentinelV3FailureCode.PROVIDER_RESPONSE_INVALID
            )
        contexts, update_flags = _validate_provider_rows(
            rows,
            fields=fields,
            period=period,
            ann_date=ann_date,
            expected_count=expected_count,
            expected_flags=expected_flags,
        )
        try:
            _source_bounded_rows_v2(
                source_bytes,
                api_name=api_name,
                expected_fields=fields,
                forbidden_text=token,
            )
        except AcquisitionError:
            raise FinancialHistorySentinelV3AcquisitionError(
                FinancialHistorySentinelV3FailureCode.CREDENTIAL_LEAK_DETECTED
            ) from None
        response_received_at = _timestamp(
            time_ns, FinancialHistorySentinelV3FailureCode.PROVIDER_TRANSPORT_FAILURE
        )
        member_key = _member_key(api_name, period, ann_date)
        files[member_key] = source_bytes
        received_at[member_key] = response_received_at
        provider_requests.append(
            {
                "api_name": api_name,
                "params": expected_body["params"],
                "fields": expected_body["fields"],
                "auth_mode": "x-api-key",
                "member_key": member_key,
                "attempts": attempts,
                "response_received_at_epoch_nanoseconds": response_received_at,
                "response_byte_count": len(source_bytes),
                "response_sha256": sha256(source_bytes),
                "observed_envelope": {"has_more": False, "count": 0},
                "item_cardinality": len(rows),
                "contexts": contexts,
                "update_flags": update_flags,
                "declared_sha256": None,
                "provider_revision_id": None,
            }
        )

    cninfo_headers = dict(_CNINFO_HEADERS)
    if any(
        forbidden in name.lower()
        for name in cninfo_headers
        for forbidden in ("authorization", "cookie", "token", "x-api-key")
    ):
        raise FinancialHistorySentinelV3AcquisitionError(
            FinancialHistorySentinelV3FailureCode.INPUT_MISMATCH
        )
    metadata_bytes, metadata_attempts = _cninfo_post_with_retries(
        cninfo_post, sleep, cninfo_headers
    )
    if cninfo_headers != dict(_CNINFO_HEADERS):
        raise FinancialHistorySentinelV3AcquisitionError(
            FinancialHistorySentinelV3FailureCode.OFFICIAL_METADATA_TRANSPORT_FAILURE
        )
    observed_metadata, selected_records = _validate_metadata(metadata_bytes, token)
    if token_bytes in metadata_bytes:
        raise FinancialHistorySentinelV3AcquisitionError(
            FinancialHistorySentinelV3FailureCode.CREDENTIAL_LEAK_DETECTED
        )
    metadata_received_at = _timestamp(
        time_ns,
        FinancialHistorySentinelV3FailureCode.OFFICIAL_METADATA_TRANSPORT_FAILURE,
    )
    files[_CNINFO_MEMBER] = metadata_bytes
    received_at[_CNINFO_MEMBER] = metadata_received_at
    official_metadata: dict[str, object] = {
        "endpoint": _CNINFO_ENDPOINT,
        "form": _CNINFO_FORM,
        "headers": dict(cninfo_headers),
        "member_key": _CNINFO_MEMBER,
        "attempts": metadata_attempts,
        "response_received_at_epoch_nanoseconds": metadata_received_at,
        "response_byte_count": len(metadata_bytes),
        "response_sha256": sha256(metadata_bytes),
        "observed_envelope": observed_metadata,
        "selected_records": selected_records,
        "declared_sha256": None,
    }

    official_documents: list[dict[str, object]] = []
    for period, _announcement_id, url, member_key, expected_bytes, expected_sha256 in _ANNUAL_REPORT_FACTS:
        source_bytes, attempts, final_url = _get_with_retries(url, get, sleep)
        if token_bytes in source_bytes:
            raise FinancialHistorySentinelV3AcquisitionError(
                FinancialHistorySentinelV3FailureCode.CREDENTIAL_LEAK_DETECTED
            )
        if (
            not source_bytes.startswith(b"%PDF-")
            or len(source_bytes) != expected_bytes
            or sha256(source_bytes) != expected_sha256
        ):
            raise FinancialHistorySentinelV3AcquisitionError(
                FinancialHistorySentinelV3FailureCode.ANNUAL_REPORT_MISMATCH
            )
        response_received_at = _timestamp(
            time_ns,
            FinancialHistorySentinelV3FailureCode.OFFICIAL_DOCUMENT_TRANSPORT_FAILURE,
        )
        files[member_key] = source_bytes
        received_at[member_key] = response_received_at
        official_documents.append(
            {
                "report_period": period,
                "requested_url": url,
                "final_url": final_url,
                "member_key": member_key,
                "attempts": attempts,
                "response_received_at_epoch_nanoseconds": response_received_at,
                "response_byte_count": len(source_bytes),
                "response_sha256": sha256(source_bytes),
                "declared_sha256": expected_sha256,
            }
        )

    snapshot = _freeze(files, received_at)
    receipt: dict[str, object] = {
        "type": "tushare_cn_a_share_financial_history_sentinel_acquisition_receipt",
        "schema_version": 3,
        "request": request.to_canonical_dict(),
        "transport_proxy_key": _PROXY_KEY,
        "transport_endpoint": endpoint,
        "provider_requests": provider_requests,
        "official_metadata": official_metadata,
        "official_documents": official_documents,
        "acquired_at_epoch_nanoseconds": max(received_at.values()),
        "snapshot": snapshot.to_canonical_dict(),
        "limitations": list(_LIMITATIONS),
        "provider_revision_id": None,
        "revision_closure_complete": False,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    published = (*files.values(), json_bytes(receipt))
    if any(token_bytes in source_bytes for source_bytes in published):
        raise FinancialHistorySentinelV3AcquisitionError(
            FinancialHistorySentinelV3FailureCode.CREDENTIAL_LEAK_DETECTED
        )
    _publish(
        final_dir,
        staging_dir,
        files,
        received_at,
        receipt,
        snapshot.to_canonical_dict(),
    )
    return receipt


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> None:
        return None


def _stdlib_cninfo_post(
    endpoint: str,
    form: tuple[tuple[str, str], ...],
    headers: dict[str, str],
) -> tuple[int, bytes]:
    if endpoint != _CNINFO_ENDPOINT or form != _CNINFO_FORM or headers != dict(_CNINFO_HEADERS):
        raise AcquisitionError("CNINFO metadata request mismatch")
    request = urllib.request.Request(
        endpoint,
        data=urllib.parse.urlencode(form).encode("ascii"),
        headers=headers,
        method="POST",
    )
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=30) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as error:
        return int(error.code), b""


def _stdlib_get(url: str) -> tuple[int, bytes, str]:
    if url not in {fact[2] for fact in _ANNUAL_REPORT_FACTS}:
        raise AcquisitionError("CNINFO document request mismatch")
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "static.cninfo.com.cn"
        or parsed.port is not None
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.startswith("/finalpage/")
        or parsed.query
        or parsed.fragment
    ):
        raise AcquisitionError("CNINFO document URL mismatch")
    request = urllib.request.Request(url, headers=dict(_CNINFO_HEADERS))
    opener = urllib.request.build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=30) as response:
            return int(response.status), response.read(), response.geturl()
    except urllib.error.HTTPError as error:
        return int(error.code), b"", error.geturl()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture frozen 000651.SZ 2018-2022 financial history evidence"
    )
    parser.add_argument("--endpoint", choices=_PROXY_ENDPOINTS, default=_PROXY_ENDPOINTS[0])
    parser.add_argument("--output-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    token = os.environ.get("TUSHARE_PROXY_TOKEN", "")
    if not token:
        raise SystemExit("TUSHARE_PROXY_TOKEN must be provided through the environment")
    try:
        receipt = acquire_tushare_cn_a_share_financial_history_sentinel_v3(
            TushareCnAShareFinancialHistorySentinelRequestV3(),
            token=token,
            endpoint=args.endpoint,
            output_dir=args.output_dir,
            proxy_post=_proxy_stdlib_post,
            cninfo_post=_stdlib_cninfo_post,
            get=_stdlib_get,
        )
    except FinancialHistorySentinelV3AcquisitionError as error:
        raise SystemExit(f"acquisition failed: {error.code.value}") from None
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
