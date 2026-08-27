from __future__ import annotations

import argparse
import ctypes
import gzip
import io
import json
import math
import os
import re
import stat
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)

from ._common import AcquisitionError, json_bytes, sha256
from .cn_a_share_tushare import _source_bounded_rows_v2
from .cn_a_share_tushare_financial_sentinel_v1 import _provider_response
from .cn_a_share_tushare_listing_source_bounded_v2 import (
    _ALLOWED_ENDPOINTS,
    _PROXY_KEY,
    _headers,
    _request_body,
)

_API_NAME = "balancesheet_vip"
_PERIOD = "20111231"
_ROOT_START_DATE = "20111231"
_ROOT_END_DATE = "20260826"
_CAPTURE_KEY = "20260827-s2c-2011-prior-balance-source-candidate-01"
_COMP_TYPE = "1"
_REPORT_TYPE = "1"
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
_SOURCE_TS_CODE = re.compile(r"\S+\.(?:SZ|SH|BJ)\Z")
MAX_SPLIT_DEPTH = 16
MAX_TOTAL_REQUESTS = 4096
MAX_TOTAL_RESPONSE_BYTES = 536_870_912
_MINIMUM_DELAY_SECONDS = 0.5
_MAX_ATTEMPTS = 3
_RETRYABLE_STATUSES = {429, *range(500, 600)}
_FALSE_FLAGS = (
    "expected_scope_extracted",
    "financial_payload_complete",
    "accounting_unit_qualified",
    "financial_availability_qualified",
    "presentation_selection_qualified",
    "financing_debt_scope_qualified",
    "provider_completeness_qualified",
    "revision_closure_complete",
    "formal_s1_qualified",
    "s2b_exact_cover_complete",
    "prior_balance_endpoint_cover_complete",
    "formal_s2_qualified",
    "strategy_authorized",
    "backtest_authorized",
    "strategy_target_authorized",
    "validation_authorized",
    "deployment_authorized",
    "decision_grade_eligible",
)
_LIMITATIONS = (
    "full-market SOURCE_SUPERSET is not the exact 1,995-key logical extraction scope",
    "zero provider rows never exclude an issuer",
    "provider announcement-date slicing is source-bounded, not revision or terminal authority",
    "financial statement revisions, supersession, and finality are not qualified",
    "accounting currency and unit authority are not established",
    "accepted financial availability is not established",
    "coherent presentation selection is not performed",
    "financing-note and debt-scope closure are not established",
    "no S2 qualification, Strategy, Backtest, Validation, or deployment authority is granted",
)

ProxyPost = Callable[
    [str, dict[str, object], dict[str, str], int],
    tuple[int, bytes],
]


@dataclass(frozen=True, slots=True)
class TushareS2c2011PriorBalanceSourceBoundedRequestV1:
    schema_version: int = 1

    def __post_init__(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("request must be the exact frozen S2C 2011 prior-balance source scope")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "tushare_s2c_2011_prior_balance_source_bounded_request_v1",
            "schema_version": 1,
            "capture_key": _CAPTURE_KEY,
            "api_name": _API_NAME,
            "period": _PERIOD,
            "start_date": _ROOT_START_DATE,
            "end_date": _ROOT_END_DATE,
            "comp_type": _COMP_TYPE,
            "report_type": _REPORT_TYPE,
            "fields": list(_BALANCE_FIELDS),
            "max_split_depth": MAX_SPLIT_DEPTH,
            "max_total_requests": MAX_TOTAL_REQUESTS,
            "max_total_response_bytes": MAX_TOTAL_RESPONSE_BYTES,
            "minimum_delay_seconds": _MINIMUM_DELAY_SECONDS,
        }


@dataclass(slots=True)
class _PageCaptureState:
    pages: list[dict[str, object]]
    logical_request_count: int = 0
    provider_attempt_count: int = 0
    total_response_bytes: int = 0
    request_started: bool = False


class _ResponseBoundaryError(AcquisitionError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


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
    return midpoint.strftime("%Y%m%d"), (midpoint + timedelta(days=1)).strftime("%Y%m%d")


def _content_length(headers: Any) -> int | None:
    value = headers.get("Content-Length") if hasattr(headers, "get") else None
    if value is None:
        return None
    if type(value) is not str or not value or not value.isascii() or not value.isdecimal():
        raise _ResponseBoundaryError("Content-Length is invalid")
    return int(value)


def _read_bounded(response: Any, ceiling: int) -> bytes:
    if type(ceiling) is not int or ceiling < 0 or not hasattr(response, "read"):
        raise _ResponseBoundaryError("response byte ceiling is invalid")
    declared = _content_length(getattr(response, "headers", None))
    if declared is not None and declared > ceiling:
        raise _ResponseBoundaryError("response byte ceiling exceeded")
    chunks: list[bytes] = []
    remaining = ceiling + 1
    while remaining:
        chunk = response.read(min(1 << 20, remaining))
        if type(chunk) is not bytes:
            raise AcquisitionError("provider transport failed")
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    source = b"".join(chunks)
    if len(source) > ceiling:
        raise _ResponseBoundaryError("response byte ceiling exceeded")
    if declared is not None and declared != len(source):
        raise _ResponseBoundaryError("Content-Length mismatch")
    return source


def _decode_transport_body(source: bytes, content_encoding: str | None, ceiling: int) -> bytes:
    if content_encoding in (None, "", "identity"):
        if len(source) > ceiling:
            raise _ResponseBoundaryError("decoded response byte ceiling exceeded")
        return source
    if type(content_encoding) is str and content_encoding.lower() == "gzip":
        try:
            with gzip.GzipFile(fileobj=io.BytesIO(source)) as stream:
                decoded = stream.read(ceiling + 1)
        except (EOFError, OSError):
            raise AcquisitionError("proxy returned invalid gzip response") from None
        if len(decoded) > ceiling:
            raise _ResponseBoundaryError("decoded response byte ceiling exceeded")
        return decoded
    raise AcquisitionError("proxy returned unsupported content encoding")


def _stdlib_post(
    url: str,
    body: dict[str, object],
    headers: dict[str, str],
    response_byte_ceiling: int,
) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url,
        data=json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(),
        headers=headers,
        method="POST",
    )
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _NoRedirect(),
    )
    try:
        with opener.open(request, timeout=30) as response:
            source = _read_bounded(response, response_byte_ceiling)
            if response.geturl() != url:
                raise AcquisitionError("proxy final URL mismatch")
            return int(response.status), _decode_transport_body(
                source,
                response.headers.get("Content-Encoding"),
                response_byte_ceiling,
            )
    except urllib.error.HTTPError as error:
        try:
            source = _read_bounded(error, response_byte_ceiling)
            return int(error.code), _decode_transport_body(
                source,
                error.headers.get("Content-Encoding") if error.headers is not None else None,
                response_byte_ceiling,
            )
        finally:
            error.close()


def _post_with_retries(
    *,
    endpoint: str,
    body: dict[str, object],
    headers: dict[str, str],
    post: ProxyPost,
    sleep: Callable[[float], object],
    state: _PageCaptureState,
) -> tuple[bytes, int]:
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        if state.provider_attempt_count >= MAX_TOTAL_REQUESTS:
            raise AcquisitionError("provider attempt request ceiling exceeded")
        state.provider_attempt_count += 1
        response_byte_ceiling = MAX_TOTAL_RESPONSE_BYTES - state.total_response_bytes
        try:
            response = post(endpoint, body, headers, response_byte_ceiling)
        except _ResponseBoundaryError:
            raise
        except Exception:  # noqa: BLE001 -- credential-bearing collaborator details are redacted.
            response = None
        if response is not None:
            if (
                type(response) is not tuple
                or len(response) != 2
                or type(response[0]) is not int
                or isinstance(response[0], bool)
                or type(response[1]) is not bytes
            ):
                raise AcquisitionError("provider transport failed")
            status, source = response
            if len(source) > response_byte_ceiling:
                raise _ResponseBoundaryError("decoded response byte ceiling exceeded")
            state.total_response_bytes += len(source)
            if status == 200:
                return source, attempt
            if status not in _RETRYABLE_STATUSES:
                raise AcquisitionError("proxy response status mismatch")
        if attempt == _MAX_ATTEMPTS:
            raise AcquisitionError("provider transport failed")
        try:
            sleep(max(_MINIMUM_DELAY_SECONDS, float(2 ** (attempt - 1))))
        except Exception:  # noqa: BLE001 -- collaborator details may contain credentials.
            raise AcquisitionError("provider transport failed") from None
    raise AssertionError("unreachable")


def _parse_page(source_bytes: bytes, token: str) -> tuple[list[list[object]], bool, int]:
    if token.encode() in source_bytes:
        raise AcquisitionError("provider response contains credential material")
    try:
        _source_bounded_rows_v2(
            source_bytes,
            api_name="financial_vip",
            expected_fields=_BALANCE_FIELDS,
            forbidden_text=token,
        )
        failure, rows, has_more, count = _provider_response(source_bytes, _BALANCE_FIELDS)
    except (AcquisitionError, RecursionError):
        raise AcquisitionError("provider response is invalid or contains credential material") from None
    if failure is not None or count != 0:
        raise AcquisitionError("provider response is invalid")
    return rows, has_more, count


def _validate_rows(rows: list[list[object]], *, start_date: str, end_date: str) -> None:
    positions = {field: index for index, field in enumerate(_BALANCE_FIELDS)}
    try:
        start = datetime.strptime(start_date, "%Y%m%d").date()
        end = datetime.strptime(end_date, "%Y%m%d").date()
    except (TypeError, ValueError):
        raise AcquisitionError("financial row scope is invalid") from None
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
    for row in rows:
        if type(row) is not list or len(row) != len(_BALANCE_FIELDS):
            raise AcquisitionError("financial row scope is invalid")
        ts_code = row[positions["ts_code"]]
        ann_date = row[positions["ann_date"]]
        f_ann_date = row[positions["f_ann_date"]]
        if (
            type(ts_code) is not str
            or _SOURCE_TS_CODE.fullmatch(ts_code) is None
            or type(ann_date) is not str
            or type(f_ann_date) is not str
            or row[positions["end_date"]] != _PERIOD
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
    state.logical_request_count += 1
    if state.request_started:
        try:
            sleep(_MINIMUM_DELAY_SECONDS)
        except Exception:  # noqa: BLE001 -- collaborator details may contain credentials.
            raise AcquisitionError("provider transport failed") from None
    else:
        state.request_started = True

    params: dict[str, object] = {
        "period": _PERIOD,
        "comp_type": _COMP_TYPE,
        "report_type": _REPORT_TYPE,
        "start_date": start_date,
        "end_date": end_date,
    }
    body = _request_body(_API_NAME, dict(params), _BALANCE_FIELDS)
    headers = _headers(token)
    expected_body = _request_body(_API_NAME, dict(params), _BALANCE_FIELDS)
    expected_headers = _headers(token)
    source_bytes, attempts = _post_with_retries(
        endpoint=endpoint,
        body=body,
        headers=headers,
        post=post,
        sleep=sleep,
        state=state,
    )
    if body != expected_body or headers != expected_headers:
        raise AcquisitionError("provider transport failed")
    response_received_at = _timestamp(time_ns)

    rows, has_more, count = _parse_page(source_bytes, token)
    _validate_rows(rows, start_date=start_date, end_date=end_date)
    member_key = f"response/tushare/{_API_NAME}/{_PERIOD}/{start_date}-{end_date}-v1.json"
    page: dict[str, object] = {
        "api_name": _API_NAME,
        "period": _PERIOD,
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


def _validate_tree(pages: list[dict[str, object]], root_member_key: str) -> dict[str, object]:
    page_by_key = {cast(str, page["member_key"]): page for page in pages}
    if not pages or len(page_by_key) != len(pages) or pages[0]["member_key"] != root_member_key:
        raise AcquisitionError("root page tree identity mismatch")
    reachable: list[str] = []
    leaf_keys: list[str] = []
    pending = [root_member_key]
    while pending:
        key = pending.pop()
        page = page_by_key.get(key)
        if page is None:
            raise AcquisitionError("root page tree identity mismatch")
        reachable.append(key)
        children = cast(list[str], page["child_member_keys"])
        params = cast(dict[str, str], page["params"])
        if page["terminal"]:
            if children:
                raise AcquisitionError("root page tree identity mismatch")
            leaf_keys.append(key)
        else:
            if len(children) != 2:
                raise AcquisitionError("root page tree identity mismatch")
            left_end, right_start = _midpoint(params["start_date"], params["end_date"])
            left, right = (page_by_key.get(child) for child in children)
            if (
                left is None
                or right is None
                or left["parent_member_key"] != key
                or right["parent_member_key"] != key
                or left["depth"] != cast(int, page["depth"]) + 1
                or right["depth"] != cast(int, page["depth"]) + 1
                or cast(dict[str, str], left["params"])["start_date"] != params["start_date"]
                or cast(dict[str, str], left["params"])["end_date"] != left_end
                or cast(dict[str, str], right["params"])["start_date"] != right_start
                or cast(dict[str, str], right["params"])["end_date"] != params["end_date"]
            ):
                raise AcquisitionError("root page tree identity mismatch")
            pending.extend(reversed(children))
    if reachable != [page["member_key"] for page in pages]:
        raise AcquisitionError("root page tree identity mismatch")
    expected_start = _ROOT_START_DATE
    for key in leaf_keys:
        page = page_by_key[key]
        params = cast(dict[str, str], page["params"])
        if params["start_date"] != expected_start:
            raise AcquisitionError("terminal leaf cover mismatch")
        expected_start = (
            datetime.strptime(params["end_date"], "%Y%m%d").date() + timedelta(days=1)
        ).strftime("%Y%m%d")
    if expected_start != (
        datetime.strptime(_ROOT_END_DATE, "%Y%m%d").date() + timedelta(days=1)
    ).strftime("%Y%m%d"):
        raise AcquisitionError("terminal leaf cover mismatch")
    return {
        "api_name": _API_NAME,
        "period": _PERIOD,
        "root_start_date": _ROOT_START_DATE,
        "root_end_date": _ROOT_END_DATE,
        "root_member_key": root_member_key,
        "page_member_keys": [page["member_key"] for page in pages],
        "terminal_leaf_member_keys": leaf_keys,
        "maximum_depth": max(cast(int, page["depth"]) for page in pages),
    }


def _freeze(files: dict[str, bytes], received_at: dict[str, int]):
    try:
        outcome = freeze_source_snapshot(
            members=tuple(
                RawSourceMember(key, value, "0644", received_at[key], None)
                for key, value in files.items()
            ),
            provenance=SourceSnapshotProvenance(
                vendor_key="tushare.pro",
                source_key=(
                    "tushare.pro.via.xiaodefa.approved-proxy."
                    "s2c-2011-prior-balance.20111231.20260826"
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
        reconstructed = {
            member.member_key: snapshot.member_bytes(member.member_key)
            for member in snapshot.members
        }
    except Exception:  # noqa: BLE001 -- snapshot internals are not acquisition output.
        raise AcquisitionError("source snapshot verification failed") from None
    if verification.failure is not None or reconstructed != files:
        raise AcquisitionError("source snapshot verification failed")
    return snapshot


def _path_components(path: Path, *, include_name: bool) -> tuple[str, tuple[str, ...]]:
    if not isinstance(path, Path):
        raise ValueError("path must be explicit Path")
    selected = path if include_name else path.parent
    parts = tuple(part for part in selected.parts if part not in {selected.anchor, "", "."})
    if ".." in parts or (include_name and path.name in {"", ".", ".."}):
        raise ValueError("path traversal is forbidden")
    return ("/" if path.is_absolute() else "."), parts


def _open_directory_path(path: Path, *, create: bool) -> int:
    anchor, components = _path_components(path, include_name=True)
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(anchor, flags)
    try:
        for component in components:
            created_identity: os.stat_result | None = None
            try:
                child_fd = os.open(component, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(component, 0o700, dir_fd=descriptor)
                    created_identity = os.stat(
                        component, dir_fd=descriptor, follow_symlinks=False
                    )
                except FileExistsError:
                    pass
                child_fd = os.open(component, flags, dir_fd=descriptor)
                try:
                    if created_identity is not None:
                        if not _same_inode(os.fstat(child_fd), created_identity):
                            raise OSError("created directory changed before open")
                        os.fchmod(child_fd, 0o700)
                        os.fsync(child_fd)
                        os.fsync(descriptor)
                except BaseException:
                    os.close(child_fd)
                    raise
            os.close(descriptor)
            descriptor = child_fd
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _open_output_parent(output: Path, *, create: bool) -> int:
    _path_components(output, include_name=False)
    if output.name in {"", ".", ".."}:
        raise ValueError("invalid output name")
    return _open_directory_path(output.parent, create=create)


def _same_inode(left: os.stat_result, right: os.stat_result) -> bool:
    return (left.st_dev, left.st_ino) == (right.st_dev, right.st_ino)


def _verify_visible_parent(output: Path, identity: os.stat_result) -> None:
    descriptor = _open_output_parent(output, create=False)
    try:
        if not _same_inode(os.fstat(descriptor), identity):
            raise OSError("visible output parent changed")
    finally:
        os.close(descriptor)


def _preflight_output(output: Path) -> int:
    parent_fd = -1
    try:
        parent_fd = _open_output_parent(output, create=True)
        identity = os.fstat(parent_fd)
        if not stat.S_ISDIR(identity.st_mode):
            raise ValueError("output parent is not a directory")
        try:
            os.stat(output.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise ValueError("output exists")
        _verify_visible_parent(output, identity)
        return parent_fd
    except (OSError, ValueError):
        if parent_fd >= 0:
            os.close(parent_fd)
        raise AcquisitionError("output path is not safe") from None


def _rename_noreplace_at(parent_fd: int, source_name: str, target_name: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise OSError("atomic no-replace rename is unavailable")
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    if renameat2(parent_fd, os.fsencode(source_name), parent_fd, os.fsencode(target_name), 1) != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), target_name)


def _open_relative_directory(root_fd: int, parts: tuple[str, ...], *, create: bool) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.dup(root_fd)
    try:
        for part in parts:
            if part in {"", ".", ".."} or "/" in part:
                raise ValueError("invalid publication member path")
            try:
                child_fd = os.open(part, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, 0o700, dir_fd=descriptor)
                created_identity = os.stat(part, dir_fd=descriptor, follow_symlinks=False)
                child_fd = os.open(part, flags, dir_fd=descriptor)
                try:
                    if not _same_inode(os.fstat(child_fd), created_identity):
                        raise OSError("created directory changed before open")
                    os.fchmod(child_fd, 0o700)
                    os.fsync(descriptor)
                except BaseException:
                    os.close(child_fd)
                    raise
            os.close(descriptor)
            descriptor = child_fd
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _readback_matches(descriptor: int, expected: bytes) -> bool:
    metadata = os.fstat(descriptor)
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    remaining = len(expected) + 1
    while remaining:
        chunk = os.read(descriptor, min(1 << 20, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return (
        stat.S_ISREG(metadata.st_mode)
        and metadata.st_size == len(expected)
        and b"".join(chunks) == expected
    )


def _write_member(root_fd: int, relative: str, source: bytes) -> os.stat_result:
    parts = tuple(relative.split("/"))
    directory_fd = _open_relative_directory(root_fd, parts[:-1], create=True)
    descriptor = -1
    try:
        descriptor = os.open(
            parts[-1],
            os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=directory_fd,
        )
        offset = 0
        while offset < len(source):
            written = os.write(descriptor, source[offset:])
            if written <= 0:
                raise OSError("publication write failed")
            offset += written
        os.fchmod(descriptor, 0o600)
        os.fsync(descriptor)
        identity = os.fstat(descriptor)
        if not _readback_matches(descriptor, source):
            raise OSError("publication readback mismatch")
        if not _same_inode(
            os.stat(parts[-1], dir_fd=directory_fd, follow_symlinks=False),
            identity,
        ):
            raise OSError("publication member pathname changed")
        os.fsync(directory_fd)
        return identity
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(directory_fd)


def _verify_members(
    root_fd: int,
    published: dict[str, bytes],
    identities: dict[str, os.stat_result],
) -> dict[str, bytes]:
    rebuilt: dict[str, bytes] = {}
    for relative, expected in published.items():
        parts = tuple(relative.split("/"))
        directory_fd = _open_relative_directory(root_fd, parts[:-1], create=False)
        descriptor = -1
        try:
            descriptor = os.open(
                parts[-1],
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=directory_fd,
            )
            if (
                not _same_inode(os.fstat(descriptor), identities[relative])
                or not _readback_matches(descriptor, expected)
            ):
                raise OSError("published member mismatch")
            rebuilt[relative] = expected
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            os.close(directory_fd)
    return rebuilt


def _publish(
    output: Path,
    parent_fd: int,
    files: dict[str, bytes],
    received_at: dict[str, int],
    receipt: dict[str, object],
) -> None:
    published = {
        **files,
        "source-snapshot.json": json_bytes(receipt["snapshot"]),
        "acquisition-receipt.json": json_bytes(receipt),
    }
    staging_name = f".{output.name}.staging-{os.getpid()}"
    staging_fd = -1
    staging_identity: os.stat_result | None = None
    try:
        parent_identity = os.fstat(parent_fd)
        _verify_visible_parent(output, parent_identity)
        for name in (output.name, staging_name):
            try:
                os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError(name)
        os.mkdir(staging_name, 0o700, dir_fd=parent_fd)
        staging_identity = os.stat(staging_name, dir_fd=parent_fd, follow_symlinks=False)
        staging_fd = os.open(
            staging_name,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        if not _same_inode(os.fstat(staging_fd), staging_identity):
            raise OSError("staging directory changed before open")
        identities: dict[str, os.stat_result] = {}
        for relative, source in sorted(
            published.items(), key=lambda item: item[0] == "acquisition-receipt.json"
        ):
            identities[relative] = _write_member(staging_fd, relative, source)
        if _verify_members(staging_fd, published, identities) != published:
            raise OSError("staged publication mismatch")
        staged_files = {key: published[key] for key in files}
        if _freeze(staged_files, received_at).to_canonical_dict() != receipt["snapshot"]:
            raise OSError("staged snapshot mismatch")
        os.fsync(staging_fd)
        if not _same_inode(
            os.stat(staging_name, dir_fd=parent_fd, follow_symlinks=False),
            staging_identity,
        ):
            raise OSError("staging pathname changed")
        _verify_visible_parent(output, parent_identity)
        _rename_noreplace_at(parent_fd, staging_name, output.name)
        published_fd = os.open(
            output.name,
            os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        try:
            if not _same_inode(os.fstat(published_fd), staging_identity):
                raise OSError("published directory inode mismatch")
            _verify_members(published_fd, published, identities)
        finally:
            os.close(published_fd)
        os.fsync(parent_fd)
        _verify_visible_parent(output, parent_identity)
    except BaseException:
        if staging_fd >= 0:
            os.close(staging_fd)
            staging_fd = -1
        try:
            os.fsync(parent_fd)
        except OSError:
            pass
        raise AcquisitionError("publication failed") from None
    finally:
        if staging_fd >= 0:
            os.close(staging_fd)


def acquire_tushare_s2c_2011_prior_balance_source_bounded_v1(
    request: TushareS2c2011PriorBalanceSourceBoundedRequestV1,
    *,
    token: str,
    endpoint: str,
    output_dir: Path,
    post: ProxyPost,
    sleep: Callable[[float], object] = time.sleep,
    time_ns: Callable[[], int] = time.time_ns,
) -> dict[str, object]:
    if (
        type(request) is not TushareS2c2011PriorBalanceSourceBoundedRequestV1
        or request != TushareS2c2011PriorBalanceSourceBoundedRequestV1()
        or not isinstance(output_dir, Path)
        or type(endpoint) is not str
        or endpoint not in _ALLOWED_ENDPOINTS
        or not callable(post)
        or not callable(sleep)
        or not callable(time_ns)
    ):
        raise AcquisitionError("acquisition input is invalid")
    if (
        type(token) is not str
        or len(token) != 56
        or token != token.strip()
        or any(character.isspace() for character in token)
        or token in os.fspath(output_dir)
        or token.encode() in json_bytes(request.to_canonical_dict())
    ):
        raise AcquisitionError("credential input is invalid")

    parent_fd = _preflight_output(output_dir)
    try:
        state = _PageCaptureState([])
        root_member_key = _capture_page_tree(
            start_date=_ROOT_START_DATE,
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
        root_tree = _validate_tree(state.pages, root_member_key)
        if state.logical_request_count != len(state.pages):
            raise AcquisitionError("logical request accounting mismatch")

        files: dict[str, bytes] = {}
        received_at: dict[str, int] = {}
        for page in state.pages:
            member_key = cast(str, page["member_key"])
            files[member_key] = cast(bytes, page.pop("_source_bytes"))
            received_at[member_key] = cast(
                int, page["response_received_at_epoch_nanoseconds"]
            )
        snapshot = _freeze(files, received_at)
        receipt: dict[str, object] = {
            "type": "tushare_s2c_2011_prior_balance_source_bounded_acquisition_receipt_v1",
            "schema_version": 1,
            "request": request.to_canonical_dict(),
            "provider_key": "tushare.pro",
            "transport_proxy_key": _PROXY_KEY,
            "transport_endpoint": endpoint,
            "provider_requests": state.pages,
            "root_tree": root_tree,
            "logical_request_count": state.logical_request_count,
            "provider_attempt_count": state.provider_attempt_count,
            "decoded_response_byte_count": state.total_response_bytes,
            "acquired_at_epoch_nanoseconds": max(received_at.values()),
            "snapshot": snapshot.to_canonical_dict(),
            "limitations": list(_LIMITATIONS),
            "source_bounded": True,
            "source_superset": True,
            "provider_revision_id": None,
            **{flag: False for flag in _FALSE_FLAGS},
        }
        publication_bytes = {
            **files,
            "source-snapshot.json": json_bytes(receipt["snapshot"]),
            "acquisition-receipt.json": json_bytes(receipt),
        }
        if any(token.encode() in source for source in publication_bytes.values()):
            raise AcquisitionError("publication contains credential material")
        _publish(output_dir, parent_fd, files, received_at, receipt)
        return receipt
    finally:
        os.close(parent_fd)


def _read_token_file(path: Path) -> str:
    if not isinstance(path, Path) or path.name in {"", ".", ".."}:
        raise AcquisitionError("token file is invalid")
    parent_fd = -1
    descriptor = -1
    try:
        parent_fd = _open_output_parent(path, create=False)
        descriptor = os.open(
            path.name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent_fd,
        )
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_IMODE(metadata.st_mode) != 0o600
            or metadata.st_size > 57
        ):
            raise ValueError("token file shape mismatch")
        source = os.read(descriptor, 58)
        if os.read(descriptor, 1):
            raise ValueError("token file shape mismatch")
        text = source.decode("ascii")
        if text.endswith("\n"):
            text = text[:-1]
        if len(text) != 56 or text != text.strip() or any(character.isspace() for character in text):
            raise ValueError("token file shape mismatch")
        return text
    except (OSError, UnicodeDecodeError, ValueError):
        raise AcquisitionError("token file is invalid") from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if parent_fd >= 0:
            os.close(parent_fd)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Capture the frozen Tushare S2C 2011 prior-balance source superset"
    )
    parser.add_argument("--endpoint", choices=_ALLOWED_ENDPOINTS, default=_ALLOWED_ENDPOINTS[0])
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    try:
        token = _read_token_file(args.token_file)
        receipt = acquire_tushare_s2c_2011_prior_balance_source_bounded_v1(
            TushareS2c2011PriorBalanceSourceBoundedRequestV1(),
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
