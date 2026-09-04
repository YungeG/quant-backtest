from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from tools.acquisition._common import AcquisitionError, sha256
from tools.acquisition.cn_a_share_tushare_000703_20240102_smoke_v1 import (
    Tushare000703DevelopmentSmokeRequestV1,
    acquire_tushare_000703_development_smoke_v1,
    verify_tushare_000703_development_smoke_v1,
)

TOKEN = "x" * 56
ROOT = Path(__file__).resolve().parents[3]
CALENDAR = ROOT / "evidence/tushare-calendar-szse-development-month-202401-v2"
MINUTE = ROOT / "evidence/tushare-minute-000703-development-month-202401/sessions/20240102"
FIELDS = {
    "stock_basic": ["ts_code", "symbol", "name", "area", "industry", "market", "exchange", "list_status", "list_date", "delist_date"],
    "daily": ["ts_code", "trade_date", "open", "high", "low", "close", "pre_close", "change", "pct_chg", "vol", "amount"],
    "stk_limit": ["trade_date", "ts_code", "up_limit", "down_limit"],
    "stock_st": ["ts_code", "trade_date", "name"],
    "suspend_d": ["ts_code", "trade_date", "suspend_timing", "suspend_type"],
}


def response(fields: list[str], rows: list[list[object]], *, terminal: bool = True, detail: str = "") -> bytes:
    return json.dumps({"request_id": "id", "code": 0, "data": {"fields": fields, "items": rows, "has_more": not terminal, "count": 0}, "msg": "", "detail": detail}, separators=(",", ":")).encode()


def valid_responses() -> dict[str, bytes]:
    return {
        "stock_basic": response(FIELDS["stock_basic"], [["000703.SZ", "000703", "恒逸石化", "浙江", "化工", "主板", "SZSE", "L", "19970528", None]]),
        "daily": response(FIELDS["daily"], [["000703.SZ", "20240102", 10, 11, 9, 10, 10, 0, 0, 100, 1000]]),
        "stk_limit": response(FIELDS["stk_limit"], [["20240102", "000703.SZ", 11, 9]]),
        "stock_st": response(FIELDS["stock_st"], []),
        "suspend_s": response(FIELDS["suspend_d"], []),
        "suspend_r": response(FIELDS["suspend_d"], []),
    }


class FakePost:
    def __init__(self, replies: dict[str, bytes]) -> None:
        self.replies = replies
        self.calls: list[dict[str, object]] = []

    def __call__(self, _url: str, body: dict[str, object], _headers: dict[str, str]) -> tuple[int, bytes]:
        self.calls.append(body)
        key = str(body["api_name"])
        if key == "suspend_d":
            key = "suspend_" + str(cast(dict[str, object], body["params"])["suspend_type"]).lower()
        return 200, self.replies[key]


def capture(tmp_path: Path, replies: dict[str, bytes] | None = None, *, calendar: Path = CALENDAR, minute: Path = MINUTE) -> tuple[Path, FakePost]:
    output = tmp_path / "capture"
    post = FakePost(replies or valid_responses())
    acquire_tushare_000703_development_smoke_v1(Tushare000703DevelopmentSmokeRequestV1(), token=TOKEN, endpoint="https://fast.xiaodefa.cn", output_dir=output, calendar_authority_dir=calendar, minute_authority_dir=minute, acquired_at_epoch_nanoseconds=1, post=post, sleep=lambda _: None)
    return output, post


def test_successful_terminal_zero_batch_is_immutable_and_verified(tmp_path: Path) -> None:
    output, post = capture(tmp_path)
    assert [body["api_name"] for body in post.calls] == ["stock_basic", "daily", "stk_limit", "stock_st", "suspend_d", "suspend_d"]
    assert [body["params"] for body in post.calls] == [
        {"ts_code": "000703.SZ", "list_status": "L"},
        {"ts_code": "000703.SZ", "start_date": "20240102", "end_date": "20240102"},
        {"ts_code": "000703.SZ", "trade_date": "20240102"},
        {"ts_code": "000703.SZ", "start_date": "20240102", "end_date": "20240102"},
        {"ts_code": "000703.SZ", "trade_date": "20240102", "suspend_type": "S"},
        {"ts_code": "000703.SZ", "trade_date": "20240102", "suspend_type": "R"},
    ]
    assert [body["fields"] for body in post.calls] == [
        ",".join(FIELDS["stock_basic"]), ",".join(FIELDS["daily"]),
        ",".join(FIELDS["stk_limit"]), ",".join(FIELDS["stock_st"]),
        ",".join(FIELDS["suspend_d"]), ",".join(FIELDS["suspend_d"]),
    ]
    assert all("token" not in body for body in post.calls)
    receipt = verify_tushare_000703_development_smoke_v1(output)
    declaration = json.loads((output / "declaration.json").read_bytes())
    assert receipt["decision_grade_eligible"] is False
    assert declaration["negative_evidence"] == {"stock_st_terminal_zero": True, "suspend_d_s_terminal_zero": True, "suspend_d_r_terminal_zero": True, "classification": "STANDARD + NORMAL", "corporate_action_absence_claimed": False}
    assert set(declaration["raw_members"]) == {"response/stock-basic.json", "response/daily.json", "response/stk-limit.json", "response/stock-st.json", "response/suspend-d-s.json", "response/suspend-d-r.json"}
    assert all(TOKEN.encode() not in item.read_bytes() for item in output.rglob("*") if item.is_file())


@pytest.mark.parametrize("mutation", [
    lambda replies: replies.__setitem__("daily", response(FIELDS["daily"], [["000703.SZ", "20240102", 10, 11, 9, 10, 10, 0, 0, 100, 1000]], terminal=False)),
    lambda replies: replies.pop("stk_limit"),
    lambda replies: replies.__setitem__("stock_basic", response(list(reversed(FIELDS["stock_basic"])), [])),
    lambda replies: replies.__setitem__("stock_st", response(FIELDS["stock_st"], [["000703.SZ", "20240102", "*ST test"]])),
    lambda replies: replies.__setitem__("suspend_s", response(FIELDS["suspend_d"], [["000703.SZ", "20240102", "09:30", "S"]])),
    lambda replies: replies.__setitem__("suspend_r", response(FIELDS["suspend_d"], [["000703.SZ", "20240102", "09:30", "R"]])),
    lambda replies: replies.__setitem__("stock_basic", response(FIELDS["stock_basic"], [["000703.SZ", "000703", "x", "x", "x", "创业板", "SZSE", "L", "19970528", None]])),
    lambda replies: replies.__setitem__("daily", response(FIELDS["daily"], [["000703.SZ", "20240102", 10, 11, 9, 10, 0, 0, 0, 100, 1000]])),
    lambda replies: replies.__setitem__("stk_limit", response(FIELDS["stk_limit"], [["20240102", "000703.SZ", 9, 10]])),
], ids=["nonterminal", "missing-member", "schema", "st-exception", "suspend-s-exception", "suspend-r-exception", "invalid-scope", "invalid-preclose", "invalid-limits"])
def test_invalid_provider_results_publish_nothing(tmp_path: Path, mutation: Any) -> None:
    replies = valid_responses()
    mutation(replies)
    with pytest.raises((AcquisitionError, KeyError)):
        capture(tmp_path, replies)
    assert not (tmp_path / "capture").exists()


def test_unavailable_or_mutated_frozen_authority_and_token_echo_publish_nothing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        capture(tmp_path, calendar=tmp_path / "missing")
    assert not (tmp_path / "capture").exists()
    bad_minute = tmp_path / "minute"
    bad_minute.mkdir()
    for source in MINUTE.rglob("*"):
        if source.is_file():
            target = bad_minute / source.relative_to(MINUTE)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
    minute_payload = json.loads((bad_minute / "response/stk-mins.json").read_bytes())
    minute_payload["data"]["items"] = minute_payload["data"]["items"][:-2]
    (bad_minute / "response/stk-mins.json").write_bytes(json.dumps(minute_payload).encode())
    with pytest.raises(AcquisitionError, match="content identity"):
        capture(tmp_path, minute=bad_minute)
    assert not (tmp_path / "capture").exists()
    replies = valid_responses()
    replies["daily"] = response(FIELDS["daily"], [], detail=TOKEN)
    with pytest.raises(AcquisitionError) as error:
        capture(tmp_path, replies)
    assert TOKEN not in str(error.value)
    assert not (tmp_path / "capture").exists()


def test_verifier_rejects_raw_hash_receipt_and_declaration_substitution(tmp_path: Path) -> None:
    output, _ = capture(tmp_path)
    (output / "response/daily.json").write_bytes(b"substituted")
    with pytest.raises(AcquisitionError, match="raw member hash"):
        verify_tushare_000703_development_smoke_v1(output)
    output, _ = capture(tmp_path / "second")
    (output / "declaration.json").write_bytes(b"{}")
    with pytest.raises(AcquisitionError, match="declaration schema or policy flags"):
        verify_tushare_000703_development_smoke_v1(output)
    output, _ = capture(tmp_path / "third")
    (output / "acquisition-receipt.json").write_bytes(b"{}")
    with pytest.raises(AcquisitionError, match="receipt schema or policy flags"):
        verify_tushare_000703_development_smoke_v1(output)


def test_verifier_rejects_receipt_and_declaration_policy_flag_substitution(tmp_path: Path) -> None:
    output, _ = capture(tmp_path)
    receipt = json.loads((output / "acquisition-receipt.json").read_bytes())
    receipt["live_eligible"] = True
    (output / "acquisition-receipt.json").write_bytes(json.dumps(receipt).encode())
    with pytest.raises(AcquisitionError, match="receipt schema or policy flags"):
        verify_tushare_000703_development_smoke_v1(output)
    output, _ = capture(tmp_path / "declaration")
    declaration = json.loads((output / "declaration.json").read_bytes())
    declaration["negative_evidence"]["corporate_action_absence_claimed"] = True
    declaration_bytes = json.dumps(declaration, sort_keys=True, separators=(",", ":")).encode()
    (output / "declaration.json").write_bytes(declaration_bytes)
    receipt = json.loads((output / "acquisition-receipt.json").read_bytes())
    receipt["declaration_sha256"] = sha256(declaration_bytes)
    (output / "acquisition-receipt.json").write_bytes(json.dumps(receipt).encode())
    with pytest.raises(AcquisitionError, match="declaration schema or policy flags"):
        verify_tushare_000703_development_smoke_v1(output)
