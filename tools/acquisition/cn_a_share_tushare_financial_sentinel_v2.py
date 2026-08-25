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
from typing import Any
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
    sha256,
)
from .cn_a_share_tushare import (
    _post_with_retries,
    _provider_body,
    _source_bounded_rows_v2,
    _stdlib_post,
)
from .cn_a_share_tushare_financial_sentinel_v1 import (
    FinancialSentinelAcquisitionError,
    _LIMITATIONS as _V1_LIMITATIONS,
    _provider_response,
    _require_safe_output,
    _validate_rows,
)

Get = Callable[[str], tuple[int, bytes, str]]


class FinancialSentinelV2FailureCode(str, Enum):
    INPUT_MISMATCH = "INPUT_MISMATCH"
    CREDENTIAL_INPUT_INVALID = "CREDENTIAL_INPUT_INVALID"
    PROVIDER_TRANSPORT_FAILURE = "PROVIDER_TRANSPORT_FAILURE"
    PROVIDER_RESPONSE_INVALID = "PROVIDER_RESPONSE_INVALID"
    PROVIDER_FIELDS_MISMATCH = "PROVIDER_FIELDS_MISMATCH"
    FINANCIAL_ROW_SCOPE_MISMATCH = "FINANCIAL_ROW_SCOPE_MISMATCH"
    CREDENTIAL_LEAK_DETECTED = "CREDENTIAL_LEAK_DETECTED"
    ANNUAL_REPORT_MISMATCH = "ANNUAL_REPORT_MISMATCH"
    PUBLICATION_CONFIRMATION_MISMATCH = "PUBLICATION_CONFIRMATION_MISMATCH"


class FinancialSentinelV2AcquisitionError(AcquisitionError):
    def __init__(
        self,
        code: FinancialSentinelV2FailureCode | SourceSnapshotFailureCode,
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
_CONFIRMATION_URL = "https://static.cninfo.com.cn/finalpage/2024-06-08/1220300051.PDF"
_CONFIRMATION_BYTES = 302_155
_CONFIRMATION_SHA256 = "sha256:a78a67865a7ea989c4fd8b053fad1aa75f36d22c10d14387800ff16b698dbc60"
_CONFIRMATION_MEMBER = "response/cninfo/publication-confirmation/1220300051.pdf"
_MAX_ATTEMPTS = 3
_PARAMS = {
    "ts_code": _TS_CODE,
    "ann_date": _ANN_DATE,
    "period": _PERIOD,
    "comp_type": "1",
}
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
    "minority_gain",
    "fin_exp_int_exp",
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
    "total_assets",
    "total_liab",
    "total_hldr_eqy_inc_min_int",
    "total_hldr_eqy_exc_min_int",
    "minority_int",
    "total_liab_hldr_eqy",
    "st_borr",
    "non_cur_liab_due_1y",
    "lt_borr",
    "bond_payable",
    "st_bonds_payable",
    "lease_liab",
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
    "depr_fa_coga_dpba",
    "use_right_asset_dep",
    "amort_intang_assets",
    "lt_amort_deferred_exp",
    "c_cash_equ_end_period",
    "free_cashflow",
    "update_flag",
)
_REQUESTS = (
    (
        "income",
        _INCOME_FIELDS,
        "response/tushare/income/000651.SZ-20231231-20240430-v2.json",
    ),
    (
        "balancesheet",
        _BALANCE_FIELDS,
        "response/tushare/balancesheet/000651.SZ-20231231-20240430-v2.json",
    ),
    (
        "cashflow",
        _CASHFLOW_FIELDS,
        "response/tushare/cashflow/000651.SZ-20231231-20240430-v2.json",
    ),
)
_DOCUMENTS = {
    _REPORT_URL: (
        _REPORT_MEMBER,
        "annual_report",
        _REPORT_BYTES,
        _REPORT_SHA256,
        FinancialSentinelV2FailureCode.ANNUAL_REPORT_MISMATCH,
    ),
    _CONFIRMATION_URL: (
        _CONFIRMATION_MEMBER,
        "confirmation",
        _CONFIRMATION_BYTES,
        _CONFIRMATION_SHA256,
        FinancialSentinelV2FailureCode.PUBLICATION_CONFIRMATION_MISMATCH,
    ),
}
_LIMITATIONS = (
    *_V1_LIMITATIONS,
    "publication confirmation is retained as raw retrospective date-only evidence",
    "confirmation semantics require a separate accepted declaration",
    "provider EBIT, EBITDA, and free cash flow are advisory only",
    "accounting unit requires a separate accepted declaration",
    "debt classification may remain incomplete",
    "no normalized revision, presentation selection, or formula evidence",
    "no five-year history, full-market coverage, or terminal-set closure",
)


@dataclass(frozen=True, slots=True)
class TushareCnAShareFinancialSourceSentinelRequestV2:
    schema_version: int = 2

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 2:
            raise ValueError("request must be the exact frozen financial sentinel v2 scope")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "tushare_cn_a_share_financial_source_sentinel_request",
            "schema_version": 2,
            "predecessor_commit": "e7e874fc58e0911b7df1cd0463387526afcb845d",
            "issuer": _ISSUER,
            "provider_security_code": _TS_CODE,
            "instrument_candidate": _INSTRUMENT,
            "company_type": "1",
            "report_period": _PERIOD,
            "announcement_date": _ANN_DATE,
            "annual_report_url": _REPORT_URL,
            "annual_report_byte_count": _REPORT_BYTES,
            "annual_report_sha256": _REPORT_SHA256,
            "confirmation_url": _CONFIRMATION_URL,
            "confirmation_byte_count": _CONFIRMATION_BYTES,
            "confirmation_sha256": _CONFIRMATION_SHA256,
            "purpose_scope": "cn-a-share.financial-source-sentinel.fixed-singleton.v2",
        }


def _map_v1_failure(code: object) -> FinancialSentinelV2FailureCode:
    try:
        return FinancialSentinelV2FailureCode(str(getattr(code, "value")))
    except ValueError:
        return FinancialSentinelV2FailureCode.PROVIDER_RESPONSE_INVALID


def _validate_v2_rows(
    rows: list[list[object]],
    *,
    fields: tuple[str, ...],
) -> dict[str, object]:
    try:
        observations = _validate_rows(rows, fields=fields)
    except FinancialSentinelAcquisitionError as error:
        raise FinancialSentinelV2AcquisitionError(
            _map_v1_failure(error.code)
        ) from None
    comp_type = fields.index("comp_type")
    if any(
        type(row[comp_type]) is not str or row[comp_type] != "1" for row in rows
    ):
        raise FinancialSentinelV2AcquisitionError(
            FinancialSentinelV2FailureCode.FINANCIAL_ROW_SCOPE_MISMATCH
        )
    return observations


def _valid_document_url(requested_url: str, value: object) -> bool:
    if type(value) is not str:
        return False
    try:
        requested = urlsplit(requested_url)
        parsed = urlsplit(value)
        return (
            parsed.scheme in {"http", "https"}
            and (
                parsed.scheme == requested.scheme
                or (requested.scheme == "http" and parsed.scheme == "https")
            )
            and parsed.hostname == "static.cninfo.com.cn"
            and parsed.port is None
            and parsed.username is None
            and parsed.password is None
            and parsed.path == requested.path
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False


def _canonical_document_url(value: object) -> str | None:
    return next(
        (
            requested_url
            for requested_url in _DOCUMENTS
            if _valid_document_url(requested_url, value)
        ),
        None,
    )


def _get_with_retries(
    url: str,
    *,
    get: Get,
    sleep: Any,
    mismatch_code: FinancialSentinelV2FailureCode,
) -> tuple[bytes, int, str]:
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            status, response_bytes, final_url = get(url)
        except Exception as error:  # noqa: BLE001 -- redact transport details.
            if isinstance(error, FinancialSentinelV2AcquisitionError):
                raise
            status, response_bytes, final_url = 0, b"", ""
        if type(status) is int and type(response_bytes) is bytes and status == 200:
            if not _valid_document_url(url, final_url):
                raise FinancialSentinelV2AcquisitionError(mismatch_code)
            return response_bytes, attempt, final_url
        if status not in {0, 429, 500, 502, 503, 504} or attempt == _MAX_ATTEMPTS:
            break
        try:
            sleep(attempt)
        except Exception:  # noqa: BLE001 -- redact retry details.
            raise FinancialSentinelV2AcquisitionError(
                FinancialSentinelV2FailureCode.PROVIDER_TRANSPORT_FAILURE
            ) from None
    raise FinancialSentinelV2AcquisitionError(
        FinancialSentinelV2FailureCode.PROVIDER_TRANSPORT_FAILURE
    )


def acquire_tushare_cn_a_share_financial_source_sentinel_v2(
    request: TushareCnAShareFinancialSourceSentinelRequestV2,
    *,
    token: str,
    output_dir: str | Path,
    post: Post,
    get: Get,
    time_ns: Any = time.time_ns,
    sleep: Any = real_sleep,
) -> dict[str, object]:
    if (
        type(request) is not TushareCnAShareFinancialSourceSentinelRequestV2
        or request != TushareCnAShareFinancialSourceSentinelRequestV2()
        or not isinstance(output_dir, (str, Path))
        or not callable(post)
        or not callable(get)
        or not callable(time_ns)
        or not callable(sleep)
    ):
        raise FinancialSentinelV2AcquisitionError(
            FinancialSentinelV2FailureCode.INPUT_MISMATCH
        )
    if type(token) is not str or not token or token != token.strip():
        raise FinancialSentinelV2AcquisitionError(
            FinancialSentinelV2FailureCode.CREDENTIAL_INPUT_INVALID
        )
    token_bytes = token.encode()
    if token_bytes in json_bytes(request.to_canonical_dict()) or token in os.fspath(
        output_dir
    ):
        raise FinancialSentinelV2AcquisitionError(
            FinancialSentinelV2FailureCode.CREDENTIAL_INPUT_INVALID
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
            response_bytes, attempts = _post_with_retries(api_name, body, post, sleep)
        except Exception:  # noqa: BLE001 -- redact transport details.
            raise FinancialSentinelV2AcquisitionError(
                FinancialSentinelV2FailureCode.PROVIDER_TRANSPORT_FAILURE
            ) from None
        try:
            response_received_at = time_ns()
        except Exception:  # noqa: BLE001 -- redact injected clock details.
            raise FinancialSentinelV2AcquisitionError(
                FinancialSentinelV2FailureCode.PROVIDER_TRANSPORT_FAILURE
            ) from None
        if type(response_received_at) is not int or response_received_at < 0:
            raise FinancialSentinelV2AcquisitionError(
                FinancialSentinelV2FailureCode.PROVIDER_TRANSPORT_FAILURE
            )
        failure, rows, has_more, count = _provider_response(response_bytes, fields)
        if failure is not None:
            raise FinancialSentinelV2AcquisitionError(_map_v1_failure(failure))
        observations = _validate_v2_rows(rows, fields=fields)
        try:
            _source_bounded_rows_v2(
                response_bytes,
                api_name=api_name,
                expected_fields=fields,
                forbidden_text=token,
            )
        except AcquisitionError:
            raise FinancialSentinelV2AcquisitionError(
                FinancialSentinelV2FailureCode.CREDENTIAL_LEAK_DETECTED
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

    official_documents: dict[str, dict[str, object]] = {}
    for url, (member_key, role, expected_bytes, expected_hash, mismatch_code) in _DOCUMENTS.items():
        source_bytes, attempts, final_url = _get_with_retries(
            url, get=get, sleep=sleep, mismatch_code=mismatch_code
        )
        try:
            response_received_at = time_ns()
        except Exception:  # noqa: BLE001 -- redact injected clock details.
            raise FinancialSentinelV2AcquisitionError(
                FinancialSentinelV2FailureCode.PROVIDER_TRANSPORT_FAILURE
            ) from None
        if type(response_received_at) is not int or response_received_at < 0:
            raise FinancialSentinelV2AcquisitionError(
                FinancialSentinelV2FailureCode.PROVIDER_TRANSPORT_FAILURE
            )
        if token_bytes in source_bytes:
            raise FinancialSentinelV2AcquisitionError(
                FinancialSentinelV2FailureCode.CREDENTIAL_LEAK_DETECTED
            )
        if (
            not source_bytes.startswith(b"%PDF-")
            or len(source_bytes) != expected_bytes
            or sha256(source_bytes) != expected_hash
        ):
            raise FinancialSentinelV2AcquisitionError(mismatch_code)
        files[member_key] = source_bytes
        received_at[member_key] = response_received_at
        official_documents[role] = {
            "requested_url": url,
            "final_url": final_url,
            "member_key": member_key,
            "attempts": attempts,
            "response_received_at_epoch_nanoseconds": response_received_at,
            "response_byte_count": len(source_bytes),
            "response_sha256": sha256(source_bytes),
            "declared_sha256": expected_hash,
        }

    outcome = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                member_key,
                source_bytes,
                "0644",
                received_at[member_key],
                _DOCUMENTS[_REPORT_URL][3]
                if member_key == _REPORT_MEMBER
                else (
                    _DOCUMENTS[_CONFIRMATION_URL][3]
                    if member_key == _CONFIRMATION_MEMBER
                    else None
                ),
            )
            for member_key, source_bytes in files.items()
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro-cninfo.com.cn",
            source_key="cn_a_share.financial_source_sentinel.000651.sz.20231231.v2",
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
        raise FinancialSentinelV2AcquisitionError(code)
    verification = verify_source_snapshot(snapshot)
    if verification.failure is not None:
        raise FinancialSentinelV2AcquisitionError(verification.failure.code)

    receipt: dict[str, object] = {
        "type": "tushare_cn_a_share_financial_source_sentinel_acquisition_receipt",
        "schema_version": 2,
        "request": request.to_canonical_dict(),
        "provider_requests": provider_requests,
        "official_documents": official_documents,
        "acquired_at_epoch_nanoseconds": max(received_at.values()),
        "snapshot": snapshot.to_canonical_dict(),
        "limitations": list(_LIMITATIONS),
        "provider_revision_id": None,
        "revision_closure_complete": False,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    published = {**files, "acquisition-receipt.json": json_bytes(receipt)}
    if any(token_bytes in value for value in published.values()):
        raise FinancialSentinelV2AcquisitionError(
            FinancialSentinelV2FailureCode.CREDENTIAL_LEAK_DETECTED
        )
    publish_directory(output_dir, published)
    return receipt


class _DocumentRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: UrlRequest,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> UrlRequest | None:
        requested_url = _canonical_document_url(req.full_url)
        if requested_url is None or not _valid_document_url(requested_url, newurl):
            mismatch = (
                _DOCUMENTS[requested_url][4]
                if requested_url is not None
                else FinancialSentinelV2FailureCode.ANNUAL_REPORT_MISMATCH
            )
            raise FinancialSentinelV2AcquisitionError(mismatch)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _stdlib_get(url: str) -> tuple[int, bytes, str]:
    if url not in _DOCUMENTS or not _valid_document_url(url, url):
        raise FinancialSentinelV2AcquisitionError(
            FinancialSentinelV2FailureCode.ANNUAL_REPORT_MISMATCH
        )
    opener = build_opener(_DocumentRedirectHandler())
    request = UrlRequest(url, headers={"User-Agent": "crypto-quant-backtest-g12a/2"})
    try:
        with opener.open(request, timeout=60) as response:
            return response.status, response.read(), response.geturl()
    except HTTPError as error:
        return error.code, error.read(), error.geturl()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture the frozen Tushare/CNINFO financial source sentinel v2"
    )
    parser.add_argument("--output-dir", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        raise SystemExit("TUSHARE_TOKEN must be provided through the environment")
    try:
        receipt = acquire_tushare_cn_a_share_financial_source_sentinel_v2(
            TushareCnAShareFinancialSourceSentinelRequestV2(),
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
