from __future__ import annotations

import argparse
import json
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

from ._common import AcquisitionError, Post, json_bytes, publish_directory, require_new_output, sha256
from .cn_a_share_tushare import (
    _post_with_retries,
    _provider_body,
    _rows,
    _stdlib_post,
)


_EXCHANGES = ("SSE", "SZSE")
_DATE = re.compile(r"20[0-9]{6}\Z")
_FIELDS = ("exchange", "cal_date", "is_open", "pretrade_date")


@dataclass(frozen=True, slots=True)
class TushareTradeCalendarRequest:
    exchange: str
    trade_date: str

    def __post_init__(self) -> None:
        if self.exchange not in _EXCHANGES:
            raise ValueError(f"exchange must be one of {_EXCHANGES}")
        if _DATE.fullmatch(self.trade_date) is None:
            raise ValueError("trade_date must be YYYYMMDD")
        try:
            datetime.strptime(self.trade_date, "%Y%m%d")
        except ValueError as error:
            raise ValueError("trade_date must be a real calendar date") from error

    def to_canonical_dict(self) -> dict[str, object]:
        return {"exchange": self.exchange, "trade_date": self.trade_date}


def acquire_trade_calendar(
    request: TushareTradeCalendarRequest,
    *,
    token: str,
    output_dir: str | Path,
    acquired_at_epoch_nanoseconds: int,
    post: Post,
    sleep: Any = real_sleep,
) -> dict[str, object]:
    if type(request) is not TushareTradeCalendarRequest:
        raise AcquisitionError("request must be exact TushareTradeCalendarRequest")
    require_new_output(output_dir)
    if type(token) is not str or not token or token != token.strip():
        raise AcquisitionError("TUSHARE_TOKEN must be canonical non-empty text")
    if type(acquired_at_epoch_nanoseconds) is not int or acquired_at_epoch_nanoseconds < 0:
        raise AcquisitionError("acquired_at_epoch_nanoseconds must be nonnegative")
    body = _provider_body(
        api_name="trade_cal",
        token=token,
        params={
            "exchange": request.exchange,
            "start_date": request.trade_date,
            "end_date": request.trade_date,
        },
        fields=_FIELDS,
    )
    response_bytes, attempts = _post_with_retries(
        "trade_cal", body, post, sleep
    )
    rows = _rows(
        response_bytes,
        api_name="trade_cal",
        expected_fields=_FIELDS,
        forbidden_text=token,
    )
    if (
        len(rows) != 1
        or rows[0][0] != request.exchange
        or str(rows[0][1]) != request.trade_date
        or rows[0][2] not in (0, 1)
        or type(rows[0][3]) is not str
        or _DATE.fullmatch(rows[0][3]) is None
    ):
        raise AcquisitionError("provider trade_cal response does not exact-cover request")
    response_hash = sha256(response_bytes)
    snapshot = freeze_source_snapshot(
        members=(
            RawSourceMember(
                "response/trade-calendar.json",
                response_bytes,
                "0644",
                acquired_at_epoch_nanoseconds,
                None,
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro",
            source_key=(
                "tushare.pro.trade_calendar."
                f"{request.exchange.lower()}.{request.trade_date}"
            ),
            license_ref="tushare.pro.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    ).snapshot
    if snapshot is None:
        raise AcquisitionError("G12A snapshot freeze failed")
    receipt: dict[str, object] = {
        "type": "tushare_trade_calendar_acquisition_receipt",
        "schema_version": 1,
        "request": request.to_canonical_dict(),
        "provider_request": {
            "api_name": "trade_cal",
            "params": body["params"],
            "fields": body["fields"],
            "attempts": attempts,
        },
        "acquired_at_epoch_nanoseconds": acquired_at_epoch_nanoseconds,
        "is_open": bool(rows[0][2]),
        "pretrade_date": rows[0][3],
        "response_sha256": response_hash,
        "snapshot": snapshot.to_canonical_dict(),
        "decision_grade_eligible": False,
        "deployment_authorized": False,
    }
    published = {
        "trade-calendar.json": response_bytes,
        "acquisition-receipt.json": json_bytes(receipt),
    }
    if any(token.encode() in value for value in published.values()):
        raise AcquisitionError("provider response unexpectedly contains credential material")
    publish_directory(output_dir, published)
    return receipt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Acquire one exact Tushare trade-calendar response"
    )
    parser.add_argument("--exchange", required=True, choices=_EXCHANGES)
    parser.add_argument("--trade-date", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        raise SystemExit("TUSHARE_TOKEN must be provided through the environment")
    try:
        receipt = acquire_trade_calendar(
            TushareTradeCalendarRequest(args.exchange, args.trade_date),
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
