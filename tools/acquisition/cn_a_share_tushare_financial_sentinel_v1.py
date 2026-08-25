from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from time import sleep as real_sleep
from typing import Any, cast
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request as UrlRequest, build_opener

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotFailureCode,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)

from ._common import (
    AcquisitionError,
    Post,
    json_bytes,
    publish_directory,
    require_new_output,
    sha256,
)
from .cn_a_share_tushare import (
    _post_with_retries,
    _provider_body,
    _source_bounded_rows_v2,
    _stdlib_post,
)

Get = Callable[[str], tuple[int, bytes, str]]


class FinancialSentinelFailureCode(str, Enum):
    INPUT_MISMATCH = "INPUT_MISMATCH"
    CREDENTIAL_INPUT_INVALID = "CREDENTIAL_INPUT_INVALID"
    PROVIDER_TRANSPORT_FAILURE = "PROVIDER_TRANSPORT_FAILURE"
    PROVIDER_RESPONSE_INVALID = "PROVIDER_RESPONSE_INVALID"
    PROVIDER_FIELDS_MISMATCH = "PROVIDER_FIELDS_MISMATCH"
    FINANCIAL_ROW_SCOPE_MISMATCH = "FINANCIAL_ROW_SCOPE_MISMATCH"
    CREDENTIAL_LEAK_DETECTED = "CREDENTIAL_LEAK_DETECTED"
    OFFICIAL_REPORT_MISMATCH = "OFFICIAL_REPORT_MISMATCH"


class FinancialSentinelAcquisitionError(AcquisitionError):
    def __init__(
        self,
        code: FinancialSentinelFailureCode | SourceSnapshotFailureCode,
    ) -> None:
        self.code = code
        super().__init__(code.value)


_TS_CODE = "000651.SZ"
_INSTRUMENT = "xshe:000651"
_ISSUER = "珠海格力电器股份有限公司"
_PERIOD = "20231231"
_ANN_DATE = "20240430"
_REPORT_URL = "http://static.cninfo.com.cn/finalpage/2024-04-30/1219928418.PDF"
_REPORT_BYTES = 3_911_496
_REPORT_SHA256 = "sha256:32ebc475a2291ce4f1b5c1a9f9da55227e03192f07e75041e976c29d213ec8aa"
_REPORT_MEMBER = "response/cninfo/annual-report/1219928418.pdf"
_MAX_ATTEMPTS = 3
_PARAMS = {"ts_code": _TS_CODE, "ann_date": _ANN_DATE, "period": _PERIOD}
_INCOME_FIELDS = (
    "ts_code",
    "ann_date",
    "f_ann_date",
    "end_date",
    "report_type",
    "comp_type",
    "revenue",
    "operate_profit",
    "total_profit",
    "income_tax",
    "n_income",
    "n_income_attr_p",
    "ebit",
    "ebitda",
    "update_flag",
)
_BALANCE_FIELDS = (
    "ts_code",
    "ann_date",
    "f_ann_date",
    "end_date",
    "report_type",
    "comp_type",
    "money_cap",
    "notes_receiv",
    "accounts_receiv",
    "inventories",
    "prepayment",
    "oth_receiv",
    "total_cur_assets",
    "fix_assets",
    "cip",
    "total_assets",
    "st_borr",
    "non_cur_liab_due_1y",
    "lt_borr",
    "bond_payable",
    "total_liab",
    "total_hldr_eqy_exc_min_int",
    "update_flag",
)
_CASHFLOW_FIELDS = (
    "ts_code",
    "ann_date",
    "f_ann_date",
    "end_date",
    "report_type",
    "comp_type",
    "n_cashflow_act",
    "c_pay_acq_const_fiolta",
    "n_cashflow_inv_act",
    "c_cash_equ_end_period",
    "update_flag",
)
_REQUESTS = (
    (
        "income",
        _INCOME_FIELDS,
        "response/tushare/income/000651.SZ-20231231-20240430.json",
    ),
    (
        "balancesheet",
        _BALANCE_FIELDS,
        "response/tushare/balancesheet/000651.SZ-20231231-20240430.json",
    ),
    (
        "cashflow",
        _CASHFLOW_FIELDS,
        "response/tushare/cashflow/000651.SZ-20231231-20240430.json",
    ),
)
_LIMITATIONS = (
    "SOURCE_BOUNDED_ONLY",
    "fixed issuer 000651.SZ and report period 20231231 only",
    "Tushare announcement time has day precision only",
    "provider initial availability time is unknown",
    "CNINFO enumeration closure is not claimed",
    "Tushare supplies no stable revision identity or parent/supersedes relationship",
    "statement revision and terminal-set closure are not claimed",
    "returned report types are observations, not a resolved final statement",
    "no absence claim for corrections, audit problems, penalties, pledges, or status events",
    "no five-year, universe, valuation, corporate-action, or execution coverage",
    "no quality score, target stream, backtest, candidate, or validation authority",
    "not decision-grade, live, or deployment eligible",
)


@dataclass(frozen=True, slots=True)
class TushareCnAShareFinancialSourceSentinelRequestV1:
    schema_version: int = 1

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("request must be the exact frozen financial sentinel v1 scope")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_financial_source_sentinel_request",
            "schema_version": 1,
            "issuer": _ISSUER,
            "provider_security_code": _TS_CODE,
            "instrument_candidate": _INSTRUMENT,
            "report_period": _PERIOD,
            "announcement_date": _ANN_DATE,
            "report_url": _REPORT_URL,
            "report_byte_count": _REPORT_BYTES,
            "report_sha256": _REPORT_SHA256,
            "purpose_scope": "cn-a-share.financial-source-sentinel.fixed-singleton.v1",
        }


def _require_safe_output(output_dir: str | Path) -> None:
    path = Path(output_dir)
    if ".." in path.parts:
        raise AcquisitionError("output path must not contain traversal")
    current = Path(path.anchor) if path.is_absolute() else Path.cwd()
    parts = path.parts[1:] if path.is_absolute() else path.parts
    for part in parts:
        current /= part
        if current.is_symlink():
            raise AcquisitionError("output path must not contain symlinks")
    require_new_output(path)


def _provider_response(
    response_bytes: bytes,
    expected_fields: tuple[str, ...],
) -> tuple[
    FinancialSentinelFailureCode | None,
    list[list[object]],
    bool,
    int,
]:
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
        payload = json.loads(
            response_bytes,
            object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return FinancialSentinelFailureCode.PROVIDER_RESPONSE_INVALID, [], False, 0
    if (
        type(payload) is not dict
        or set(payload) != {"request_id", "code", "data", "msg", "detail"}
        or type(payload["request_id"]) is not str
        or not payload["request_id"]
        or payload["request_id"] != payload["request_id"].strip()
        or type(payload["code"]) is not int
        or payload["code"] != 0
        or type(payload["msg"]) is not str
        or type(payload["detail"]) is not str
        or type(payload["data"]) is not dict
    ):
        return FinancialSentinelFailureCode.PROVIDER_RESPONSE_INVALID, [], False, 0
    data = payload["data"]
    if (
        set(data) != {"fields", "items", "has_more", "count"}
        or type(data["fields"]) is not list
        or type(data["items"]) is not list
        or type(data["has_more"]) is not bool
        or type(data["count"]) is not int
        or any(
            type(item) is not list or len(item) != len(data["fields"])
            for item in data["items"]
        )
    ):
        return FinancialSentinelFailureCode.PROVIDER_RESPONSE_INVALID, [], False, 0
    if data["fields"] != list(expected_fields):
        return FinancialSentinelFailureCode.PROVIDER_FIELDS_MISMATCH, [], False, 0
    return (
        None,
        cast(list[list[object]], data["items"]),
        cast(bool, data["has_more"]),
        cast(int, data["count"]),
    )


def _validate_rows(
    rows: list[list[object]],
    *,
    fields: tuple[str, ...],
) -> dict[str, object]:
    if not rows:
        raise FinancialSentinelAcquisitionError(
            FinancialSentinelFailureCode.FINANCIAL_ROW_SCOPE_MISMATCH
        )
    positions = {field: index for index, field in enumerate(fields)}
    if any(
        type(row[positions["ts_code"]]) is not str
        or row[positions["ts_code"]] != _TS_CODE
        or type(row[positions["ann_date"]]) is not str
        or row[positions["ann_date"]] != _ANN_DATE
        or type(row[positions["end_date"]]) is not str
        or row[positions["end_date"]] != _PERIOD
        for row in rows
    ):
        raise FinancialSentinelAcquisitionError(
            FinancialSentinelFailureCode.FINANCIAL_ROW_SCOPE_MISMATCH
        )
    serialized = [
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) for row in rows
    ]
    identity_fields = (
        "ts_code",
        "ann_date",
        "f_ann_date",
        "end_date",
        "report_type",
        "comp_type",
    )
    by_identity: dict[tuple[object, ...], set[str]] = {}
    for row, encoded in zip(rows, serialized, strict=True):
        identity = tuple(row[positions[field]] for field in identity_fields)
        by_identity.setdefault(identity, set()).add(encoded)
    return {
        "row_count": len(rows),
        "report_types": sorted(
            {
                str(row[positions["report_type"]])
                for row in rows
                if row[positions["report_type"]] is not None
            }
        ),
        "duplicate_row_count": len(serialized) - len(set(serialized)),
        "conflicting_identity_count": sum(
            len(values) > 1 for values in by_identity.values()
        ),
    }


def _valid_report_url(value: object) -> bool:
    if type(value) is not str:
        return False
    try:
        parsed = urlsplit(value)
        expected = urlsplit(_REPORT_URL)
        return (
            parsed.scheme in {"http", "https"}
            and parsed.hostname == "static.cninfo.com.cn"
            and parsed.port is None
            and parsed.username is None
            and parsed.password is None
            and parsed.path == expected.path
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False


def _get_with_retries(url: str, get: Get, sleep: Any) -> tuple[bytes, int, str]:
    if not callable(get) or not callable(sleep):
        raise FinancialSentinelAcquisitionError(
            FinancialSentinelFailureCode.INPUT_MISMATCH
        )
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            status, response_bytes, final_url = get(url)
        except Exception as error:  # noqa: BLE001 -- redact transport details.
            if isinstance(error, FinancialSentinelAcquisitionError):
                raise
            status, response_bytes, final_url = 0, b"", ""
        if type(status) is int and type(response_bytes) is bytes and status == 200:
            if not _valid_report_url(final_url):
                raise FinancialSentinelAcquisitionError(
                    FinancialSentinelFailureCode.OFFICIAL_REPORT_MISMATCH
                )
            return response_bytes, attempt, final_url
        if status not in {0, 429, 500, 502, 503, 504} or attempt == _MAX_ATTEMPTS:
            break
        try:
            sleep(attempt)
        except Exception:  # noqa: BLE001 -- redact injected retry details.
            raise FinancialSentinelAcquisitionError(
                FinancialSentinelFailureCode.PROVIDER_TRANSPORT_FAILURE
            ) from None
    raise FinancialSentinelAcquisitionError(
        FinancialSentinelFailureCode.PROVIDER_TRANSPORT_FAILURE
    )


def acquire_tushare_cn_a_share_financial_source_sentinel_v1(
    request: TushareCnAShareFinancialSourceSentinelRequestV1,
    *,
    token: str,
    output_dir: str | Path,
    post: Post,
    get: Get,
    time_ns: Any = time.time_ns,
    sleep: Any = real_sleep,
) -> dict[str, object]:
    if (
        type(request) is not TushareCnAShareFinancialSourceSentinelRequestV1
        or request != TushareCnAShareFinancialSourceSentinelRequestV1()
        or not isinstance(output_dir, (str, Path))
        or not callable(post)
        or not callable(get)
        or not callable(time_ns)
        or not callable(sleep)
    ):
        raise FinancialSentinelAcquisitionError(
            FinancialSentinelFailureCode.INPUT_MISMATCH
        )
    if type(token) is not str or not token or token != token.strip():
        raise FinancialSentinelAcquisitionError(
            FinancialSentinelFailureCode.CREDENTIAL_INPUT_INVALID
        )
    token_bytes = token.encode()
    if (
        token_bytes in json_bytes(request.to_canonical_dict())
        or token in os.fspath(output_dir)
    ):
        raise FinancialSentinelAcquisitionError(
            FinancialSentinelFailureCode.CREDENTIAL_INPUT_INVALID
        )
    _require_safe_output(output_dir)

    files: dict[str, bytes] = {}
    received_at: dict[str, int] = {}
    provider_requests: list[dict[str, object]] = []

    for api_name, fields, member_key in _REQUESTS:
        body = _provider_body(
            api_name=api_name,
            token=token,
            params=dict(_PARAMS),
            fields=fields,
        )
        try:
            response_bytes, attempts = _post_with_retries(
                api_name, body, post, sleep
            )
        except Exception:  # noqa: BLE001 -- redact transport/collaborator details.
            raise FinancialSentinelAcquisitionError(
                FinancialSentinelFailureCode.PROVIDER_TRANSPORT_FAILURE
            ) from None
        try:
            response_received_at = time_ns()
        except Exception:  # noqa: BLE001 -- redact injected clock details.
            raise FinancialSentinelAcquisitionError(
                FinancialSentinelFailureCode.PROVIDER_TRANSPORT_FAILURE
            ) from None
        if type(response_received_at) is not int or response_received_at < 0:
            raise FinancialSentinelAcquisitionError(
                FinancialSentinelFailureCode.PROVIDER_TRANSPORT_FAILURE
            )
        failure, rows, has_more, count = _provider_response(response_bytes, fields)
        if failure is not None:
            raise FinancialSentinelAcquisitionError(failure)
        observations = _validate_rows(rows, fields=fields)
        try:
            _source_bounded_rows_v2(
                response_bytes,
                api_name=api_name,
                expected_fields=fields,
                forbidden_text=token,
            )
        except AcquisitionError:
            raise FinancialSentinelAcquisitionError(
                FinancialSentinelFailureCode.CREDENTIAL_LEAK_DETECTED
            ) from None
        files[member_key] = response_bytes
        received_at[member_key] = response_received_at
        provider_requests.append(
            {
                "api_name": api_name,
                "params": body["params"],
                "fields": body["fields"],
                "member_key": member_key,
                "attempts": attempts,
                "response_received_at_epoch_nanoseconds": response_received_at,
                "response_byte_count": len(response_bytes),
                "response_sha256": sha256(response_bytes),
                "observed_envelope": {"has_more": has_more, "count": count},
                "observed_rows": observations,
                "declared_sha256": None,
                "provider_revision_id": None,
            }
        )

    report_bytes, report_attempts, final_url = _get_with_retries(
        _REPORT_URL, get, sleep
    )
    try:
        report_received_at = time_ns()
    except Exception:  # noqa: BLE001 -- redact injected clock details.
        raise FinancialSentinelAcquisitionError(
            FinancialSentinelFailureCode.PROVIDER_TRANSPORT_FAILURE
        ) from None
    if type(report_received_at) is not int or report_received_at < 0:
        raise FinancialSentinelAcquisitionError(
            FinancialSentinelFailureCode.PROVIDER_TRANSPORT_FAILURE
        )
    if token_bytes in report_bytes:
        raise FinancialSentinelAcquisitionError(
            FinancialSentinelFailureCode.CREDENTIAL_LEAK_DETECTED
        )
    if (
        not report_bytes.startswith(b"%PDF-")
        or len(report_bytes) != _REPORT_BYTES
        or sha256(report_bytes) != _REPORT_SHA256
    ):
        raise FinancialSentinelAcquisitionError(
            FinancialSentinelFailureCode.OFFICIAL_REPORT_MISMATCH
        )
    files[_REPORT_MEMBER] = report_bytes
    received_at[_REPORT_MEMBER] = report_received_at

    outcome = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                member_key,
                source_bytes,
                "0644",
                received_at[member_key],
                _REPORT_SHA256 if member_key == _REPORT_MEMBER else None,
            )
            for member_key, source_bytes in files.items()
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro-cninfo.com.cn",
            source_key="cn_a_share.financial_source_sentinel.000651.sz.20231231.v1",
            license_ref="tushare.pro.terms-cninfo.public-disclosure",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    )
    snapshot = outcome.snapshot
    if snapshot is None:
        code = (
            outcome.failure.code
            if outcome.failure is not None
            else SourceSnapshotFailureCode.ACQUISITION_FAILED
        )
        raise FinancialSentinelAcquisitionError(code)
    verification = verify_source_snapshot(snapshot)
    if verification.failure is not None:
        raise FinancialSentinelAcquisitionError(verification.failure.code)

    receipt: dict[str, object] = {
        "type": "tushare_cn_a_share_financial_source_sentinel_acquisition_receipt",
        "schema_version": 1,
        "request": request.to_canonical_dict(),
        "provider_requests": provider_requests,
        "official_report": {
            "requested_url": _REPORT_URL,
            "final_url": final_url,
            "member_key": _REPORT_MEMBER,
            "attempts": report_attempts,
            "response_received_at_epoch_nanoseconds": report_received_at,
            "response_byte_count": len(report_bytes),
            "response_sha256": sha256(report_bytes),
            "declared_sha256": _REPORT_SHA256,
        },
        "acquired_at_epoch_nanoseconds": max(received_at.values()),
        "snapshot": snapshot.to_canonical_dict(),
        "limitations": list(_LIMITATIONS),
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    published = {**files, "acquisition-receipt.json": json_bytes(receipt)}
    if any(token_bytes in value for value in published.values()):
        raise FinancialSentinelAcquisitionError(
            FinancialSentinelFailureCode.CREDENTIAL_LEAK_DETECTED
        )
    publish_directory(output_dir, published)
    return receipt


class _ReportRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: UrlRequest,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> UrlRequest | None:
        if not _valid_report_url(newurl):
            raise FinancialSentinelAcquisitionError(
                FinancialSentinelFailureCode.OFFICIAL_REPORT_MISMATCH
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _stdlib_get(url: str) -> tuple[int, bytes, str]:
    if not _valid_report_url(url):
        raise FinancialSentinelAcquisitionError(
            FinancialSentinelFailureCode.OFFICIAL_REPORT_MISMATCH
        )
    opener = build_opener(_ReportRedirectHandler())
    request = UrlRequest(url, headers={"User-Agent": "crypto-quant-backtest-g12a/1"})
    try:
        with opener.open(request, timeout=60) as response:
            return response.status, response.read(), response.geturl()
    except HTTPError as error:
        return error.code, error.read(), error.geturl()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture the frozen Tushare/CNINFO financial source sentinel v1"
    )
    parser.add_argument("--output-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        raise SystemExit("TUSHARE_TOKEN must be provided through the environment")
    try:
        receipt = acquire_tushare_cn_a_share_financial_source_sentinel_v1(
            TushareCnAShareFinancialSourceSentinelRequestV1(),
            token=token,
            output_dir=args.output_dir,
            post=_stdlib_post,
            get=_stdlib_get,
        )
    except (AcquisitionError, ValueError) as error:
        raise SystemExit(f"acquisition failed: {error}") from None
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
