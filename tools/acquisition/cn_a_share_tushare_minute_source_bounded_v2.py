from __future__ import annotations

import argparse
import json
import math
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from time import sleep as real_sleep

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshot,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
    verify_source_snapshot,
)

from ._common import AcquisitionError, json_bytes, publish_directory, require_new_output, sha256
from .cn_a_share_tushare_authority import _authority_rows
from .cn_a_share_tushare_listing_source_bounded_v2 import (
    _ALLOWED_ENDPOINTS,
    _PROXY_KEY,
    _headers,
    _post_with_retries,
    _request_body,
    _stdlib_post,
)

_TS_CODE = "000703.SZ"
_FREQ = "5min"
_FIELDS = ("ts_code", "trade_time", "close", "open", "high", "low", "vol", "amount")

ProxyPost = Callable[[str, dict[str, object], dict[str, str]], tuple[int, bytes]]


@dataclass(frozen=True, slots=True)
class TushareMinuteSourceBoundedRequestV2:
    ts_code: str
    trade_date: str
    freq: str

    def __post_init__(self) -> None:
        try:
            datetime.strptime(self.trade_date, "%Y%m%d")
        except (TypeError, ValueError) as error:
            raise ValueError("trade_date must be a real YYYYMMDD date") from error
        if (self.ts_code, self.freq) != (_TS_CODE, _FREQ):
            raise ValueError("request must match fixed 000703.SZ / 5min scope")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "type": "tushare_minute_source_bounded_request_v2",
            "schema_version": 2,
            "ts_code": self.ts_code,
            "trade_date": self.trade_date,
            "freq": self.freq,
        }


def _expected_trade_times(trade_date: str) -> tuple[str, ...]:
    try:
        date = datetime.strptime(trade_date, "%Y%m%d").strftime("%Y-%m-%d")
        labels = ["09:30:00"]
        for start, stop in (("09:35:00", "11:30:00"), ("13:05:00", "15:00:00")):
            current = datetime.strptime(f"{date} {start}", "%Y-%m-%d %H:%M:%S")
            end = datetime.strptime(f"{date} {stop}", "%Y-%m-%d %H:%M:%S")
            while current <= end:
                labels.append(current.strftime("%H:%M:%S"))
                current += timedelta(minutes=5)
    except (TypeError, ValueError) as error:
        raise ValueError("trade_date must be a real YYYYMMDD date") from error
    return tuple(f"{date} {label}" for label in labels)


def _number(value: object) -> float:
    if type(value) not in (int, float):
        raise ValueError("not a numeric value")
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError("not a numeric value") from error
    if not math.isfinite(number):
        raise ValueError("not a finite numeric value")
    return number


def _is_number(value: object) -> bool:
    try:
        _number(value)
    except ValueError:
        return False
    return True


def _validate_rows(rows: list[list[object]], request: TushareMinuteSourceBoundedRequestV2) -> None:
    expected = _expected_trade_times(request.trade_date)
    times = [row[1] for row in rows]
    if any(type(value) is not str for value in times):
        raise AcquisitionError("stk_mins response has invalid session labels")
    if len(set(times)) != len(times):
        raise AcquisitionError("stk_mins response has duplicate session labels")
    if len(rows) != len(expected) or set(times) != set(expected):
        raise AcquisitionError("stk_mins response has missing or off-grid session labels")
    for row in rows:
        ts_code, _, close, open_, high, low, vol, amount = row
        if ts_code != _TS_CODE:
            raise AcquisitionError("stk_mins response has mismatched ts_code")
        if not all(_is_number(value) for value in (close, open_, high, low, vol, amount)):
            raise AcquisitionError("stk_mins response has non-numeric OHLCV")
        close_f, open_f, high_f, low_f, vol_f, amount_f = (
            _number(value) for value in (close, open_, high, low, vol, amount)
        )
        if (
            min(close_f, open_f, high_f, low_f) <= 0
            or high_f < max(close_f, open_f)
            or low_f > min(close_f, open_f)
            or vol_f < 0
            or amount_f < 0
        ):
            raise AcquisitionError("stk_mins response has invalid OHLCV")


def verify_tushare_minute_source_bounded_receipt_v2(
    receipt_bytes: bytes, snapshot: SourceSnapshot, expected_receipt_hash: str
) -> dict[str, object]:
    """Verify one retained fixed 000703.SZ 5-minute source receipt."""
    if type(receipt_bytes) is not bytes or type(expected_receipt_hash) is not str:
        raise AcquisitionError("receipt and expected receipt hash have invalid types")
    if sha256(receipt_bytes) != expected_receipt_hash:
        raise AcquisitionError("receipt hash does not match expected receipt hash")
    def unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise ValueError(f"invalid JSON constant {value}")

    try:
        receipt = json.loads(
            receipt_bytes, object_pairs_hook=unique_object, parse_constant=reject_constant
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise AcquisitionError("receipt is not valid JSON") from error
    if type(receipt) is not dict:
        raise AcquisitionError("receipt must be a JSON object")
    fields = {
        "type", "schema_version", "source_bounded", "development_only", "request",
        "provider_key", "transport_proxy_key", "transport_endpoint", "provider_requests",
        "acquired_at_epoch_nanoseconds", "snapshot", "anchor_trade_time",
        "anchor_strategy_eligible", "strategy_trade_time_count", "decision_grade_eligible",
        "live_eligible", "deployment_authorized",
    }
    if set(receipt) != fields or receipt.get("type") != "tushare_minute_source_bounded_acquisition_receipt_v2" or receipt.get("schema_version") != 2:
        raise AcquisitionError("receipt has unexpected type or schema")
    request_data = receipt.get("request")
    try:
        request = TushareMinuteSourceBoundedRequestV2(
            request_data["ts_code"], request_data["trade_date"], request_data["freq"]
        )
    except (KeyError, TypeError, ValueError) as error:
        raise AcquisitionError("receipt has invalid request") from error
    if request_data != request.to_canonical_dict() or receipt.get("provider_key") != "tushare.pro" or receipt.get("transport_proxy_key") != _PROXY_KEY or receipt.get("transport_endpoint") not in _ALLOWED_ENDPOINTS:
        raise AcquisitionError("receipt request or transport mismatch")
    flags = ("source_bounded", "development_only", "anchor_strategy_eligible", "decision_grade_eligible", "live_eligible", "deployment_authorized")
    if tuple(receipt.get(flag) for flag in flags) != (True, True, False, False, False, False) or any(type(receipt.get(flag)) is not bool for flag in flags):
        raise AcquisitionError("receipt has invalid development flags")
    acquired_at = receipt.get("acquired_at_epoch_nanoseconds")
    if type(acquired_at) is not int or acquired_at < 0:
        raise AcquisitionError("receipt acquisition time is invalid")
    try:
        outcome = verify_source_snapshot(snapshot)
    except (AttributeError, TypeError, ValueError) as error:
        raise AcquisitionError("receipt has invalid source snapshot") from error
    member_key = "response/stk-mins.json"
    endpoint = receipt.get("transport_endpoint")
    expected_provenance = SourceSnapshotProvenance(
        vendor_key="tushare.pro",
        source_key=(
            "tushare.pro.via.xiaodefa.approved-proxy."
            f"{endpoint.removeprefix('https://')}.stk_mins.000703.sz.{request.trade_date}.5min"
        ),
        license_ref="tushare.pro.terms",
        retention_policy_ref="backtest.acquisition.candidate",
    )
    if outcome.snapshot != snapshot or receipt.get("snapshot") != snapshot.to_canonical_dict() or snapshot.provenance != expected_provenance or len(snapshot.members) != 1:
        raise AcquisitionError("receipt snapshot identity does not match source snapshot")
    member = snapshot.members[0]
    if member.member_key != member_key or member.declared_sha256 is not None or member.acquired_at_epoch_nanoseconds != acquired_at:
        raise AcquisitionError("receipt snapshot member mismatch")
    requests = receipt.get("provider_requests")
    expected_params = {"ts_code": _TS_CODE, "freq": _FREQ, "start_date": _expected_trade_times(request.trade_date)[0], "end_date": _expected_trade_times(request.trade_date)[-1]}
    request_fields = {"api_name", "params", "fields", "member_key", "auth_mode", "attempts", "response_byte_count", "response_sha256", "response_acquired_at_epoch_nanoseconds", "returned_row_count", "provider_revision_id", "declared_sha256"}
    if type(requests) is not list or len(requests) != 1 or type(requests[0]) is not dict:
        raise AcquisitionError("receipt has invalid provider requests")
    provider_request = requests[0]
    try:
        source = snapshot.member_bytes(member_key)
    except (KeyError, TypeError, ValueError) as error:
        raise AcquisitionError("receipt snapshot has no minute response") from error
    if (set(provider_request) != request_fields or provider_request.get("api_name") != "stk_mins" or provider_request.get("params") != expected_params or provider_request.get("fields") != ",".join(_FIELDS) or provider_request.get("member_key") != member_key or provider_request.get("auth_mode") != "x-api-key" or type(provider_request.get("attempts")) is not int or provider_request["attempts"] not in range(1, 4) or type(provider_request.get("response_byte_count")) is not int or type(provider_request.get("returned_row_count")) is not int or provider_request.get("provider_revision_id") is not None or provider_request.get("declared_sha256") is not None or provider_request.get("response_byte_count") != len(source) or provider_request.get("response_sha256") != sha256(source) or provider_request.get("response_acquired_at_epoch_nanoseconds") != acquired_at or type(provider_request.get("response_acquired_at_epoch_nanoseconds")) is not int or member.content_hash != sha256(source)):
        raise AcquisitionError("receipt provider request mismatch")
    rows = _authority_rows(source, api_name="stk_mins", expected_fields=_FIELDS, forbidden_text="\0")
    _validate_rows(rows, request)
    if receipt.get("anchor_trade_time") != _expected_trade_times(request.trade_date)[0] or receipt.get("strategy_trade_time_count") != 48 or provider_request.get("returned_row_count") != 49:
        raise AcquisitionError("receipt minute session labels mismatch")
    return receipt


def acquire_tushare_minute_source_bounded_v2(
    request: TushareMinuteSourceBoundedRequestV2,
    *,
    endpoint: str,
    output_dir: str | Path,
    post: ProxyPost,
    clock: Callable[[], int] = time.time_ns,
    sleep: Callable[[float], object] = real_sleep,
) -> dict[str, object]:
    if type(request) is not TushareMinuteSourceBoundedRequestV2:
        raise AcquisitionError("request must be exact TushareMinuteSourceBoundedRequestV2")
    require_new_output(output_dir)
    if endpoint not in _ALLOWED_ENDPOINTS:
        raise AcquisitionError("proxy endpoint is not approved")
    token = os.environ.get("TUSHARE_PROXY_TOKEN", "")
    if not isinstance(token, str) or len(token) != 56 or token != token.strip() or any(char.isspace() for char in token):
        raise AcquisitionError("TUSHARE_PROXY_TOKEN must be exact 56-character text")

    session_date = datetime.strptime(request.trade_date, "%Y%m%d").strftime("%Y-%m-%d")
    params = {
        "ts_code": request.ts_code,
        "freq": request.freq,
        "start_date": f"{session_date} 09:30:00",
        "end_date": f"{session_date} 15:00:00",
    }
    body = _request_body("stk_mins", params, _FIELDS)
    source, attempts = _post_with_retries(
        "stk_mins",
        endpoint=endpoint,
        body=body,
        headers=_headers(token),
        post=post,
        sleep=sleep,
    )
    response_acquired_at_epoch_nanoseconds = clock()
    if type(response_acquired_at_epoch_nanoseconds) is not int or response_acquired_at_epoch_nanoseconds < 0:
        raise AcquisitionError("clock must return a nonnegative integer nanosecond timestamp")
    rows = _authority_rows(source, api_name="stk_mins", expected_fields=_FIELDS, forbidden_text=token)
    _validate_rows(rows, request)

    member_key = "response/stk-mins.json"
    snapshot = freeze_source_snapshot(
        members=(RawSourceMember(member_key, source, "0644", response_acquired_at_epoch_nanoseconds, None),),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro",
            source_key=(
                "tushare.pro.via.xiaodefa.approved-proxy."
                f"{endpoint.removeprefix('https://')}.stk_mins.000703.sz.{request.trade_date}.5min"
            ),
            license_ref="tushare.pro.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot
    if snapshot is None:
        raise AcquisitionError("SourceSnapshot freeze failed")

    receipt: dict[str, object] = {
        "type": "tushare_minute_source_bounded_acquisition_receipt_v2",
        "schema_version": 2,
        "source_bounded": True,
        "development_only": True,
        "request": request.to_canonical_dict(),
        "provider_key": "tushare.pro",
        "transport_proxy_key": _PROXY_KEY,
        "transport_endpoint": endpoint,
        "provider_requests": [{
            "api_name": "stk_mins", "params": params, "fields": ",".join(_FIELDS),
            "member_key": member_key, "auth_mode": "x-api-key", "attempts": attempts,
            "response_byte_count": len(source), "response_sha256": sha256(source),
            "response_acquired_at_epoch_nanoseconds": response_acquired_at_epoch_nanoseconds,
            "returned_row_count": len(rows), "provider_revision_id": None, "declared_sha256": None,
        }],
        "acquired_at_epoch_nanoseconds": response_acquired_at_epoch_nanoseconds,
        "snapshot": snapshot.to_canonical_dict(),
        "anchor_trade_time": _expected_trade_times(request.trade_date)[0],
        "anchor_strategy_eligible": False,
        "strategy_trade_time_count": len(rows) - 1,
        "decision_grade_eligible": False,
        "live_eligible": False,
        "deployment_authorized": False,
    }
    published = {member_key: source, "acquisition-receipt.json": json_bytes(receipt)}
    if any(token.encode() in value for value in published.values()):
        raise AcquisitionError("proxy response unexpectedly contains credential material")
    publish_directory(output_dir, published)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Acquire one bounded development-only Tushare 5-minute session")
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--endpoint", choices=_ALLOWED_ENDPOINTS, default=_ALLOWED_ENDPOINTS[0])
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not os.environ.get("TUSHARE_PROXY_TOKEN"):
        raise SystemExit("TUSHARE_PROXY_TOKEN must be provided through the environment")
    try:
        receipt = acquire_tushare_minute_source_bounded_v2(
            TushareMinuteSourceBoundedRequestV2(_TS_CODE, args.trade_date, _FREQ),
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
