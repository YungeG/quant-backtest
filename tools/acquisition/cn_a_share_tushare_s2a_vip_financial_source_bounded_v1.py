from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)

from . import _common
from ._common import AcquisitionError, json_bytes, sha256
from .cn_a_share_tushare import _source_bounded_rows_v2
from .cn_a_share_tushare_financial_sentinel_v1 import (
    _provider_response,
    _require_safe_output,
)
from .cn_a_share_tushare_listing_source_bounded_v2 import (
    ProxyPost,
    _ALLOWED_ENDPOINTS,
    _PROXY_KEY,
    _headers,
    _post_with_retries,
    _request_body,
    _stdlib_post,
)

_API_ORDER = ("income_vip", "balancesheet_vip", "cashflow_vip")
_PERIOD_ORDER = tuple(f"{year}1231" for year in range(2012, 2025))
_ROOT_END_DATE = "20260826"
_CAPTURE_KEY = "20260826-s2a-vip-financial-candidate-01"
_SOURCE_TS_CODE = re.compile(r"[^\s.]+\.(?:SZ|SH|BJ)\Z")
_COMP_TYPE = "1"
_REPORT_TYPE = "1"
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
_FIELD_SETS = {
    "income_vip": _INCOME_FIELDS,
    "balancesheet_vip": _BALANCE_FIELDS,
    "cashflow_vip": _CASHFLOW_FIELDS,
}
MAX_SPLIT_DEPTH = 16
MAX_TOTAL_REQUESTS = 4096
MAX_TOTAL_RESPONSE_BYTES = 536_870_912
_MINIMUM_DELAY_SECONDS = 0.5
_LIMITATIONS = (
    "full-market source superset is not exact S1 or S2 scope",
    "provider announcement-date slicing is source-bounded, not revision or terminal authority",
    "lease_liab is unavailable from the captured VIP balance schema",
    "provider computed EBIT, EBITDA, and free_cashflow are advisory",
    "expected S1 extraction and missing-member closure are not performed",
    "financial statement revisions, supersession, and finality are not qualified",
    "accounting currency and unit authority are not established",
    "accepted financial availability is not established",
    "coherent presentation selection is not performed",
    "financing-note and debt-scope closure are not established",
    "no S2 qualification, Strategy, Validation, or deployment authority is granted",
)


@dataclass(frozen=True, slots=True)
class TushareS2aVipFinancialSourceBoundedRequestV1:
    schema_version: int = 1

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("request must be the exact frozen S2A VIP financial source scope")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "tushare_s2a_vip_financial_source_bounded_request_v1",
            "schema_version": 1,
            "capture_key": _CAPTURE_KEY,
            "api_order": list(_API_ORDER),
            "period_order": list(_PERIOD_ORDER),
            "root_end_date": _ROOT_END_DATE,
            "field_sets": {
                api_name: list(_FIELD_SETS[api_name]) for api_name in _API_ORDER
            },
            "max_split_depth": MAX_SPLIT_DEPTH,
            "max_total_requests": MAX_TOTAL_REQUESTS,
            "max_total_response_bytes": MAX_TOTAL_RESPONSE_BYTES,
        }


@dataclass(slots=True)
class _PageCaptureState:
    pages: list[dict[str, object]]
    request_count: int
    total_response_bytes: int
    request_started: bool


def _timestamp(time_ns: Callable[[], int]) -> int:
    try:
        value = time_ns()
    except Exception:  # noqa: BLE001 -- collaborator details may contain credentials.
        raise AcquisitionError("acquisition clock failed") from None
    if type(value) is not int or value < 0:
        raise AcquisitionError("acquisition clock failed")
    return value


def _midpoint(start_date: str, end_date: str) -> tuple[str, str]:
    try:
        start = datetime.strptime(start_date, "%Y%m%d").date()
        end = datetime.strptime(end_date, "%Y%m%d").date()
    except (TypeError, ValueError):
        raise AcquisitionError("announcement interval is invalid") from None
    if start >= end:
        raise AcquisitionError("announcement interval cannot be split")
    midpoint = start + timedelta(days=(end - start).days // 2)
    return midpoint.strftime("%Y%m%d"), (midpoint + timedelta(days=1)).strftime(
        "%Y%m%d"
    )


def _parse_page(
    source_bytes: bytes,
    expected_fields: tuple[str, ...],
    token: str,
) -> tuple[list[list[object]], bool, int]:
    if token.encode() in source_bytes:
        raise AcquisitionError("provider response contains credential material")
    try:
        _source_bounded_rows_v2(
            source_bytes,
            api_name="financial_vip",
            expected_fields=expected_fields,
            forbidden_text=token,
        )
    except (AcquisitionError, RecursionError):
        raise AcquisitionError("provider response is invalid or contains credential material") from None
    try:
        failure, rows, has_more, count = _provider_response(
            source_bytes, expected_fields
        )
    except RecursionError:
        raise AcquisitionError("provider response is invalid") from None
    if failure is not None or count != 0:
        raise AcquisitionError("provider response is invalid")
    return rows, has_more, count


def _validate_rows(
    rows: list[list[object]],
    *,
    api_name: str,
    period: str,
    start_date: str,
    end_date: str,
) -> None:
    fields = _FIELD_SETS.get(api_name)
    if fields is None:
        raise AcquisitionError("financial API is invalid")
    positions = {field: index for index, field in enumerate(fields)}
    try:
        start = datetime.strptime(start_date, "%Y%m%d").date()
        end = datetime.strptime(end_date, "%Y%m%d").date()
        datetime.strptime(period, "%Y%m%d")
    except (TypeError, ValueError):
        raise AcquisitionError("financial row scope is invalid") from None
    for row in rows:
        if type(row) is not list or len(row) != len(fields):
            raise AcquisitionError("financial row scope is invalid")
        ts_code = row[positions["ts_code"]]
        ann_date = row[positions["ann_date"]]
        f_ann_date = row[positions["f_ann_date"]]
        if (
            type(ts_code) is not str
            or _SOURCE_TS_CODE.fullmatch(ts_code) is None
            or type(ann_date) is not str
            or type(f_ann_date) is not str
            or row[positions["end_date"]] != period
            or type(row[positions["end_date"]]) is not str
            or row[positions["report_type"]] != _REPORT_TYPE
            or type(row[positions["report_type"]]) is not str
            or row[positions["comp_type"]] != _COMP_TYPE
            or type(row[positions["comp_type"]]) is not str
            or row[positions["update_flag"]] not in {"0", "1"}
            or type(row[positions["update_flag"]]) is not str
        ):
            raise AcquisitionError("financial row scope is invalid")
        try:
            announcement = datetime.strptime(ann_date, "%Y%m%d").date()
            datetime.strptime(f_ann_date, "%Y%m%d")
        except ValueError:
            raise AcquisitionError("financial row scope is invalid") from None
        if not start <= announcement <= end:
            raise AcquisitionError("financial row scope is invalid")
        context_positions = {
            positions[name]
            for name in (
                "ts_code",
                "ann_date",
                "f_ann_date",
                "end_date",
                "report_type",
                "comp_type",
                "update_flag",
            )
        }
        if any(
            value is not None
            and type(value) is not int
            and not (type(value) is float and math.isfinite(value))
            for index, value in enumerate(row)
            if index not in context_positions
        ):
            raise AcquisitionError("financial row scope is invalid")


def _capture_page_tree(
    *,
    api_name: str,
    period: str,
    fields: tuple[str, ...],
    start_date: str,
    end_date: str,
    parent_member_key: str | None,
    depth: int,
    state: _PageCaptureState,
    token: str,
    endpoint: str,
    post: ProxyPost,
    sleep: Callable[[float], object],
    time_ns: Callable[[], int],
) -> str:
    if state.request_count >= MAX_TOTAL_REQUESTS:
        raise AcquisitionError("logical request ceiling exceeded")
    state.request_count += 1
    if state.request_started:
        try:
            sleep(_MINIMUM_DELAY_SECONDS)
        except Exception:  # noqa: BLE001 -- redact injected delay details.
            raise AcquisitionError("provider transport failed") from None
    else:
        state.request_started = True

    params: dict[str, object] = {
        "period": period,
        "comp_type": _COMP_TYPE,
        "report_type": _REPORT_TYPE,
        "start_date": start_date,
        "end_date": end_date,
    }
    body = _request_body(api_name, dict(params), fields)
    headers = _headers(token)
    expected_body = _request_body(api_name, dict(params), fields)
    expected_headers = _headers(token)
    try:
        source_bytes, attempts = _post_with_retries(
            api_name,
            endpoint=endpoint,
            body=body,
            headers=headers,
            post=post,
            sleep=sleep,
        )
    except Exception:  # noqa: BLE001 -- transport and retry details are redacted.
        raise AcquisitionError("provider transport failed") from None
    if body != expected_body or headers != expected_headers:
        raise AcquisitionError("provider transport failed")
    response_received_at = _timestamp(time_ns)
    state.total_response_bytes += len(source_bytes)
    if state.total_response_bytes > MAX_TOTAL_RESPONSE_BYTES:
        raise AcquisitionError("decoded response byte ceiling exceeded")

    rows, has_more, count = _parse_page(source_bytes, fields, token)
    _validate_rows(
        rows,
        api_name=api_name,
        period=period,
        start_date=start_date,
        end_date=end_date,
    )
    member_key = (
        f"response/tushare/{api_name}/{period}/"
        f"{start_date}-{end_date}-v1.json"
    )
    page: dict[str, object] = {
        "api_name": api_name,
        "period": period,
        "params": params,
        "fields": expected_body["fields"],
        "member_key": member_key,
        "parent_member_key": parent_member_key,
        "depth": depth,
        "attempts": attempts,
        "response_received_at_epoch_nanoseconds": response_received_at,
        "response_byte_count": len(source_bytes),
        "response_sha256": sha256(source_bytes),
        "returned_row_count": len(rows),
        "observed_envelope": {"has_more": has_more, "count": count},
        "terminal": not has_more,
        "child_member_keys": [],
        "provider_revision_id": None,
        "declared_sha256": None,
        "_source_bytes": source_bytes,
    }
    state.pages.append(page)
    if not has_more:
        return member_key
    if start_date == end_date:
        raise AcquisitionError("one-day announcement interval cannot be split")
    if depth >= MAX_SPLIT_DEPTH:
        raise AcquisitionError("split depth ceiling exceeded")
    left_end, right_start = _midpoint(start_date, end_date)
    left_key = _capture_page_tree(
        api_name=api_name,
        period=period,
        fields=fields,
        start_date=start_date,
        end_date=left_end,
        parent_member_key=member_key,
        depth=depth + 1,
        state=state,
        token=token,
        endpoint=endpoint,
        post=post,
        sleep=sleep,
        time_ns=time_ns,
    )
    right_key = _capture_page_tree(
        api_name=api_name,
        period=period,
        fields=fields,
        start_date=right_start,
        end_date=end_date,
        parent_member_key=member_key,
        depth=depth + 1,
        state=state,
        token=token,
        endpoint=endpoint,
        post=post,
        sleep=sleep,
        time_ns=time_ns,
    )
    page["child_member_keys"] = [left_key, right_key]
    return member_key


def acquire_tushare_s2a_vip_financial_source_bounded_v1(
    request: TushareS2aVipFinancialSourceBoundedRequestV1,
    *,
    token: str,
    endpoint: str,
    output_dir: str | Path,
    post: ProxyPost,
    sleep: Callable[[float], object] = time.sleep,
    time_ns: Callable[[], int] = time.time_ns,
) -> dict[str, object]:
    if (
        type(request) is not TushareS2aVipFinancialSourceBoundedRequestV1
        or request != TushareS2aVipFinancialSourceBoundedRequestV1()
        or not isinstance(output_dir, (str, Path))
        or type(endpoint) is not str
        or endpoint not in _ALLOWED_ENDPOINTS
        or not callable(post)
        or not callable(sleep)
        or not callable(time_ns)
    ):
        raise AcquisitionError("acquisition input is invalid")
    try:
        _require_safe_output(output_dir)
    except (AcquisitionError, OSError, ValueError):
        raise AcquisitionError("output path is not safe") from None
    if (
        type(token) is not str
        or len(token) != 56
        or token != token.strip()
        or any(character.isspace() for character in token)
        or token in os.fspath(output_dir)
        or token.encode() in json_bytes(request.to_canonical_dict())
    ):
        raise AcquisitionError("credential input is invalid")

    state = _PageCaptureState([], 0, 0, False)
    root_trees: list[dict[str, object]] = []
    for api_name in _API_ORDER:
        fields = _FIELD_SETS[api_name]
        for period in _PERIOD_ORDER:
            first_page = len(state.pages)
            root_member_key = _capture_page_tree(
                api_name=api_name,
                period=period,
                fields=fields,
                start_date=period,
                end_date=_ROOT_END_DATE,
                parent_member_key=None,
                depth=0,
                state=state,
                token=token,
                endpoint=endpoint,
                post=post,
                sleep=sleep,
                time_ns=time_ns,
            )
            pages = state.pages[first_page:]
            root_trees.append(
                {
                    "api_name": api_name,
                    "period": period,
                    "root_start_date": period,
                    "root_end_date": _ROOT_END_DATE,
                    "root_member_key": root_member_key,
                    "page_member_keys": [page["member_key"] for page in pages],
                    "terminal_leaf_member_keys": [
                        page["member_key"] for page in pages if page["terminal"]
                    ],
                    "maximum_depth": max(cast(int, page["depth"]) for page in pages),
                }
            )

    page_by_key = {cast(str, page["member_key"]): page for page in state.pages}
    expected_roots = [
        (api_name, period) for api_name in _API_ORDER for period in _PERIOD_ORDER
    ]
    if [
        (tree["api_name"], tree["period"]) for tree in root_trees
    ] != expected_roots or len(page_by_key) != len(state.pages):
        raise AcquisitionError("root page tree identity mismatch")
    for tree in root_trees:
        page_keys = cast(list[str], tree["page_member_keys"])
        leaf_keys = cast(list[str], tree["terminal_leaf_member_keys"])
        if (
            not page_keys
            or page_keys[0] != tree["root_member_key"]
            or set(page_keys) - page_by_key.keys()
            or page_by_key[page_keys[0]]["parent_member_key"] is not None
            or page_by_key[page_keys[0]]["depth"] != 0
            or tree["maximum_depth"]
            != max(cast(int, page_by_key[key]["depth"]) for key in page_keys)
        ):
            raise AcquisitionError("root page tree identity mismatch")
        reachable: list[str] = []
        pending = [cast(str, tree["root_member_key"])]
        while pending:
            key = pending.pop()
            reachable.append(key)
            page = page_by_key.get(key)
            if page is None:
                raise AcquisitionError("root page tree identity mismatch")
            children = cast(list[str], page["child_member_keys"])
            if page["terminal"]:
                if children:
                    raise AcquisitionError("root page tree identity mismatch")
            else:
                if len(children) != 2:
                    raise AcquisitionError("root page tree identity mismatch")
                left_end, right_start = _midpoint(
                    cast(dict[str, str], page["params"])["start_date"],
                    cast(dict[str, str], page["params"])["end_date"],
                )
                left, right = (page_by_key.get(child) for child in children)
                if (
                    left is None
                    or right is None
                    or left["parent_member_key"] != key
                    or right["parent_member_key"] != key
                    or left["depth"] != cast(int, page["depth"]) + 1
                    or right["depth"] != cast(int, page["depth"]) + 1
                    or cast(dict[str, str], left["params"])["start_date"]
                    != cast(dict[str, str], page["params"])["start_date"]
                    or cast(dict[str, str], left["params"])["end_date"] != left_end
                    or cast(dict[str, str], right["params"])["start_date"]
                    != right_start
                    or cast(dict[str, str], right["params"])["end_date"]
                    != cast(dict[str, str], page["params"])["end_date"]
                ):
                    raise AcquisitionError("root page tree identity mismatch")
                pending.extend(reversed(children))
        if reachable != page_keys:
            raise AcquisitionError("root page tree identity mismatch")
        leaves = [page_by_key[key] for key in leaf_keys]
        if not leaves:
            raise AcquisitionError("terminal leaf cover mismatch")
        expected_start = cast(str, tree["root_start_date"])
        for leaf in leaves:
            params = cast(dict[str, str], leaf["params"])
            if (
                not leaf["terminal"]
                or params["start_date"] != expected_start
                or leaf["api_name"] != tree["api_name"]
                or leaf["period"] != tree["period"]
            ):
                raise AcquisitionError("terminal leaf cover mismatch")
            expected_start = (
                datetime.strptime(params["end_date"], "%Y%m%d").date()
                + timedelta(days=1)
            ).strftime("%Y%m%d")
        if expected_start != (
            datetime.strptime(cast(str, tree["root_end_date"]), "%Y%m%d").date()
            + timedelta(days=1)
        ).strftime("%Y%m%d"):
            raise AcquisitionError("terminal leaf cover mismatch")

    files: dict[str, bytes] = {}
    received_at: dict[str, int] = {}
    for page in state.pages:
        member_key = cast(str, page["member_key"])
        files[member_key] = cast(bytes, page.pop("_source_bytes"))
        received_at[member_key] = cast(
            int, page["response_received_at_epoch_nanoseconds"]
        )
    try:
        outcome = freeze_source_snapshot(
            members=tuple(
                RawSourceMember(
                    member_key,
                    source_bytes,
                    "0644",
                    received_at[member_key],
                    None,
                )
                for member_key, source_bytes in files.items()
            ),
            provenance=SourceSnapshotProvenance(
                vendor_key="tushare.pro",
                source_key=(
                    "tushare.pro.via.xiaodefa.approved-proxy."
                    "s2a-vip-financial.2012-2024.20260826"
                ),
                license_ref="tushare.pro.terms",
                retention_policy_ref="backtest.acquisition.candidate",
            ),
        )
    except Exception:  # noqa: BLE001 -- snapshot internals are not acquisition output.
        raise AcquisitionError("source snapshot freeze failed") from None
    if outcome.snapshot is None:
        raise AcquisitionError("source snapshot freeze failed")
    snapshot = outcome.snapshot
    try:
        verification = verify_source_snapshot(snapshot)
    except Exception:  # noqa: BLE001 -- verification details are redacted.
        raise AcquisitionError("source snapshot verification failed") from None
    if verification.failure is not None:
        raise AcquisitionError("source snapshot verification failed")

    receipt: dict[str, object] = {
        "type": "tushare_s2a_vip_financial_source_bounded_acquisition_receipt_v1",
        "schema_version": 1,
        "request": request.to_canonical_dict(),
        "provider_key": "tushare.pro",
        "transport_proxy_key": _PROXY_KEY,
        "transport_endpoint": endpoint,
        "provider_requests": state.pages,
        "root_trees": root_trees,
        "acquired_at_epoch_nanoseconds": max(received_at.values()),
        "snapshot": snapshot.to_canonical_dict(),
        "limitations": list(_LIMITATIONS),
        "source_bounded": True,
        "source_superset": True,
        "expected_scope_extracted": False,
        "financial_payload_complete": False,
        "accounting_unit_qualified": False,
        "financial_availability_qualified": False,
        "presentation_selection_qualified": False,
        "financing_debt_scope_qualified": False,
        "provider_completeness_qualified": False,
        "revision_closure_complete": False,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
        "provider_revision_id": None,
    }
    published = {
        **files,
        "source-snapshot.json": json_bytes(snapshot.to_canonical_dict()),
        "acquisition-receipt.json": json_bytes(receipt),
    }
    if any(token.encode() in source_bytes for source_bytes in published.values()):
        raise AcquisitionError("publication contains credential material")
    try:
        _common.publish_directory(output_dir, published)
    except Exception:  # noqa: BLE001 -- publication paths and internals are redacted.
        raise AcquisitionError("publication failed") from None
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture the frozen Tushare S2A VIP financial source superset"
    )
    parser.add_argument("--endpoint", choices=_ALLOWED_ENDPOINTS, default=_ALLOWED_ENDPOINTS[0])
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    token = os.environ.get("TUSHARE_PROXY_TOKEN", "")
    if not token:
        raise SystemExit("TUSHARE_PROXY_TOKEN must be provided through the environment")
    try:
        receipt = acquire_tushare_s2a_vip_financial_source_bounded_v1(
            TushareS2aVipFinancialSourceBoundedRequestV1(),
            token=token,
            endpoint=args.endpoint,
            output_dir=args.output_dir,
            post=_stdlib_post,
        )
    except (AcquisitionError, ValueError) as error:
        raise SystemExit(f"acquisition failed: {error}") from None
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
