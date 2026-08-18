from __future__ import annotations

import argparse
import json
import math
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from time import sleep as real_sleep
from typing import Any

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
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
    _rows,
    _stdlib_post,
)


_TS_CODE = re.compile(r"[0-9]{6}\.(?:SZ|SH|BJ)\Z")
_DATE = re.compile(r"20[0-9]{6}\Z")
_HISTORICAL_DATE = re.compile(r"(?:19|20)[0-9]{6}\Z")
_STOCK_FIELDS = (
    "ts_code",
    "symbol",
    "name",
    "area",
    "industry",
    "market",
    "exchange",
    "list_status",
    "list_date",
    "delist_date",
)
_NAME_FIELDS = (
    "ts_code",
    "name",
    "start_date",
    "end_date",
    "ann_date",
    "change_reason",
)
_ADJ_FIELDS = ("ts_code", "trade_date", "adj_factor")
_DIVIDEND_FIELDS = (
    "ts_code",
    "end_date",
    "ann_date",
    "div_proc",
    "stk_div",
    "stk_bo_rate",
    "stk_co_rate",
    "cash_div",
    "cash_div_tax",
    "record_date",
    "ex_date",
    "pay_date",
    "div_listdate",
    "imp_ann_date",
    "base_date",
    "base_share",
)


@dataclass(frozen=True, slots=True)
class TushareAuthorityRequest:
    ts_code: str
    trade_date: str
    previous_trade_date: str
    next_trade_date: str

    def __post_init__(self) -> None:
        if _TS_CODE.fullmatch(self.ts_code) is None:
            raise ValueError("ts_code must be a canonical SZ/SH/BJ Tushare code")
        for name, value in (
            ("trade_date", self.trade_date),
            ("previous_trade_date", self.previous_trade_date),
            ("next_trade_date", self.next_trade_date),
        ):
            if _DATE.fullmatch(value) is None:
                raise ValueError(f"{name} must be YYYYMMDD")
            try:
                datetime.strptime(value, "%Y%m%d")
            except ValueError as error:
                raise ValueError(f"{name} must be a real calendar date") from error
        if not self.previous_trade_date < self.trade_date < self.next_trade_date:
            raise ValueError("trade dates must be strictly ordered")

    def to_canonical_dict(self) -> dict[str, object]:
        return {
            "ts_code": self.ts_code,
            "trade_date": self.trade_date,
            "previous_trade_date": self.previous_trade_date,
            "next_trade_date": self.next_trade_date,
        }


def acquire_listing_corporate_action_authority(
    request: TushareAuthorityRequest,
    *,
    token: str,
    output_dir: str | Path,
    acquired_at_epoch_nanoseconds: int,
    post: Post,
    sleep: Any = real_sleep,
) -> dict[str, object]:
    if type(request) is not TushareAuthorityRequest:
        raise AcquisitionError("request must be exact TushareAuthorityRequest")
    require_new_output(output_dir)
    if type(token) is not str or not token or token != token.strip():
        raise AcquisitionError("TUSHARE_TOKEN must be canonical non-empty text")
    if (
        type(acquired_at_epoch_nanoseconds) is not int
        or acquired_at_epoch_nanoseconds < 0
    ):
        raise AcquisitionError("acquired_at_epoch_nanoseconds must be nonnegative")

    specifications = (
        ("stock_basic", {"ts_code": request.ts_code}, _STOCK_FIELDS),
        ("namechange", {"ts_code": request.ts_code}, _NAME_FIELDS),
        (
            "adj_factor",
            {
                "ts_code": request.ts_code,
                "start_date": request.previous_trade_date,
                "end_date": request.next_trade_date,
            },
            _ADJ_FIELDS,
        ),
        (
            "dividend",
            {"ts_code": request.ts_code, "ex_date": request.trade_date},
            _DIVIDEND_FIELDS,
        ),
    )
    captured: dict[
        str,
        tuple[dict[str, object], bytes, int, list[list[object]]],
    ] = {}
    for api_name, params, fields in specifications:
        body = _provider_body(
            api_name=api_name,
            token=token,
            params=params,
            fields=fields,
        )
        response_bytes, attempts = _post_with_retries(
            api_name,
            body,
            post,
            sleep,
        )
        rows = _rows(
            response_bytes,
            api_name=api_name,
            expected_fields=fields,
            forbidden_text=token,
        )
        captured[api_name] = (body, response_bytes, attempts, rows)

    stock_rows = captured["stock_basic"][3]
    if len(stock_rows) != 1 or stock_rows[0][0] != request.ts_code:
        raise AcquisitionError("provider stock_basic response does not exact-cover request")
    stock = stock_rows[0]
    list_date = stock[8]
    delist_date = stock[9]
    if (
        stock[7] != "L"
        or type(list_date) is not str
        or _HISTORICAL_DATE.fullmatch(list_date) is None
        or list_date > request.trade_date
        or (
            delist_date is not None
            and (
                type(delist_date) is not str
                or _HISTORICAL_DATE.fullmatch(delist_date) is None
                or delist_date < request.trade_date
            )
        )
    ):
        raise AcquisitionError("provider stock_basic listing interval does not cover request")

    name_rows = captured["namechange"][3]
    if any(row[0] != request.ts_code for row in name_rows):
        raise AcquisitionError("provider namechange response does not exact-cover request")
    covering_names = [
        row
        for row in name_rows
        if type(row[2]) is str
        and _HISTORICAL_DATE.fullmatch(row[2]) is not None
        and row[2] <= request.trade_date
        and (
            row[3] is None
            or (
                type(row[3]) is str
                and _HISTORICAL_DATE.fullmatch(row[3]) is not None
                and request.trade_date <= row[3]
            )
        )
    ]
    if len(covering_names) != 1:
        raise AcquisitionError("provider namechange response has no unique target interval")

    adj_rows = captured["adj_factor"][3]
    expected_dates = {
        request.previous_trade_date,
        request.trade_date,
        request.next_trade_date,
    }
    if (
        len(adj_rows) != 3
        or {row[1] for row in adj_rows} != expected_dates
        or any(
            row[0] != request.ts_code
            or type(row[1]) is not str
            or type(row[2]) not in (int, float)
            or not math.isfinite(row[2])
            or row[2] <= 0
            for row in adj_rows
        )
    ):
        raise AcquisitionError("provider adj_factor response does not exact-cover request")

    dividend_rows = captured["dividend"][3]
    if any(
        row[0] != request.ts_code or row[10] != request.trade_date
        for row in dividend_rows
    ):
        raise AcquisitionError("provider dividend response does not exact-cover request")

    files = {
        "response/stock-basic.json": captured["stock_basic"][1],
        "response/namechange.json": captured["namechange"][1],
        "response/adj-factor.json": captured["adj_factor"][1],
        "response/dividend-ex-date.json": captured["dividend"][1],
    }
    snapshot = freeze_source_snapshot(
        members=tuple(
            RawSourceMember(
                member_key,
                source_bytes,
                "0644",
                acquired_at_epoch_nanoseconds,
                None,
            )
            for member_key, source_bytes in sorted(files.items())
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro",
            source_key=(
                "tushare.pro.listing_corporate_action_authority."
                f"{request.ts_code.lower()}.{request.trade_date}"
            ),
            license_ref="tushare.pro.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot
    if snapshot is None:
        raise AcquisitionError("G12A snapshot freeze failed")

    provider_requests = []
    for api_name, _, _ in specifications:
        body, _, attempts, _ = captured[api_name]
        provider_requests.append(
            {
                "api_name": api_name,
                "params": body["params"],
                "fields": body["fields"],
                "attempts": attempts,
            }
        )
    receipt: dict[str, object] = {
        "type": "tushare_authority_acquisition_receipt",
        "schema_version": 1,
        "request": request.to_canonical_dict(),
        "provider_requests": provider_requests,
        "acquired_at_epoch_nanoseconds": acquired_at_epoch_nanoseconds,
        "listing_row_count": len(stock_rows),
        "namechange_row_count": len(name_rows),
        "adj_factor_row_count": len(adj_rows),
        "target_ex_date_dividend_row_count": len(dividend_rows),
        "listing_interval_covers_trade_date": True,
        "name_interval_covers_trade_date": True,
        "response_sha256": {
            api_name: sha256(captured[api_name][1])
            for api_name, _, _ in specifications
        },
        "snapshot": snapshot.to_canonical_dict(),
        "provider_revision_id": None,
        "revision_closure_complete": False,
        "historical_listing_status_qualified": False,
        "corporate_action_lifecycle_qualified": False,
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    published = {
        "stock-basic.json": files["response/stock-basic.json"],
        "namechange.json": files["response/namechange.json"],
        "adj-factor.json": files["response/adj-factor.json"],
        "dividend-ex-date.json": files["response/dividend-ex-date.json"],
        "acquisition-receipt.json": json_bytes(receipt),
    }
    if any(token.encode() in value for value in published.values()):
        raise AcquisitionError("provider response unexpectedly contains credential material")
    publish_directory(output_dir, published)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Acquire exact Tushare listing and corporate-action source bytes"
    )
    parser.add_argument("--ts-code", required=True)
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--previous-trade-date", required=True)
    parser.add_argument("--next-trade-date", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        raise SystemExit("TUSHARE_TOKEN must be provided through the environment")
    try:
        receipt = acquire_listing_corporate_action_authority(
            TushareAuthorityRequest(
                args.ts_code.upper(),
                args.trade_date,
                args.previous_trade_date,
                args.next_trade_date,
            ),
            token=token,
            output_dir=args.output_dir,
            acquired_at_epoch_nanoseconds=time.time_ns(),
            post=_stdlib_post,
        )
    except (AcquisitionError, ValueError) as error:
        raise SystemExit(f"acquisition failed: {error}") from None
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
