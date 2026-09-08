from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).parents[3]
FIXTURE = ROOT / "fixtures/market_data/providers/tushare/cn-a-share-authority-v1"
HASHES = {
    "acquisition-receipt.json": "5f2e6f2c3870cdc26c93a2e15e5842888b890cb8d20ad5d5b16ed19882771276",
    "adj-factor.json": "4830a62041922615a68d9b31b5a9ee608fdeb3835e52ba308fede59622422df8",
    "dividend-ex-date.json": "cc1a888c81aef5e93097951eb25ea14e14744e1a5cf3b3da2eea5cb561609a7d",
    "namechange.json": "9a4982b500c54001160f958c618a99092d7859d56da21dbaea58963e89db82d4",
    "stock-basic.json": "93cba2aa17cc927cf454d4de962d2f18a099a9576cf044add502626df3075af4",
}


def test_real_tushare_authority_capture_is_exact_and_unqualified() -> None:
    assert {path.name for path in FIXTURE.iterdir()} == set(HASHES)
    for name, expected in HASHES.items():
        assert hashlib.sha256((FIXTURE / name).read_bytes()).hexdigest() == expected

    receipt = json.loads((FIXTURE / "acquisition-receipt.json").read_text())
    assert receipt["request"] == {
        "next_trade_date": "20240103",
        "previous_trade_date": "20231229",
        "trade_date": "20240102",
        "ts_code": "000001.SZ",
    }
    assert receipt["acquired_at_epoch_nanoseconds"] == 1_787_021_168_783_113_919
    assert receipt["listing_row_count"] == 1
    assert receipt["namechange_row_count"] == 4
    assert receipt["adj_factor_row_count"] == 3
    assert receipt["target_ex_date_dividend_row_count"] == 0
    assert receipt["listing_interval_covers_trade_date"] is True
    assert receipt["name_interval_covers_trade_date"] is True
    assert receipt["provider_revision_id"] is None
    assert receipt["revision_closure_complete"] is False
    assert receipt["historical_listing_status_qualified"] is False
    assert receipt["corporate_action_lifecycle_qualified"] is False
    assert receipt["decision_grade_eligible"] is False
    assert receipt["deployment_authorized"] is False
    assert receipt["snapshot"]["snapshot_id"] == (
        "sha256:bd8ae548949696f1c98f8a20b5c8653f64121fc2eee61c1ff2ac21a97d248c0d"
    )
    assert receipt["snapshot"]["provenance_hash"] == (
        "sha256:f0e938a25f952cc5ba6ce5300975927a7956099ce4fd899cb99cf21538d9e8ca"
    )
    assert {
        member["member_key"]: member["content_hash"]
        for member in receipt["snapshot"]["members"]
    } == {
        "response/adj-factor.json": "sha256:" + HASHES["adj-factor.json"],
        "response/dividend-ex-date.json": "sha256:" + HASHES["dividend-ex-date.json"],
        "response/namechange.json": "sha256:" + HASHES["namechange.json"],
        "response/stock-basic.json": "sha256:" + HASHES["stock-basic.json"],
    }

    stock = json.loads((FIXTURE / "stock-basic.json").read_text())["data"]["items"]
    names = json.loads((FIXTURE / "namechange.json").read_text())["data"]["items"]
    factors = json.loads((FIXTURE / "adj-factor.json").read_text())["data"]["items"]
    dividends = json.loads((FIXTURE / "dividend-ex-date.json").read_text())["data"]["items"]
    assert stock == [[
        "000001.SZ",
        "000001",
        "平安银行",
        "深圳",
        "银行",
        "主板",
        "SZSE",
        "L",
        "19910403",
        None,
    ]]
    assert len(names) == 4
    assert [row for row in names if row[2] <= "20240102" and row[3] is None] == [
        ["000001.SZ", "平安银行", "20120802", None, "20120120", "其他"]
    ]
    assert {(row[1], row[2]) for row in factors} == {
        ("20231229", 116.713),
        ("20240102", 116.713),
        ("20240103", 116.713),
    }
    assert dividends == []
    assert "token" not in "".join(
        (FIXTURE / name).read_text().lower() for name in HASHES
    )
