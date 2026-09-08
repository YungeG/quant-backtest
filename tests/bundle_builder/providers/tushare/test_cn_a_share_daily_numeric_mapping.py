from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from crypto_quant_domain import canonical_sha256


FIXTURE = (
    Path(__file__).parents[3]
    / "fixtures/market_data/providers/tushare/cn-a-share-daily-listing-v1"
)
SOURCE = FIXTURE / "daily.json"
EVENT_TIME = (
    FIXTURE.parent / "cn-a-share-trade-calendar-v1/daily-event-time.expected.json"
)
EXPECTED = json.loads((FIXTURE / "numeric-mapping.expected.json").read_text())
_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")


def _units(raw: str, scale: int) -> int:
    assert _DECIMAL.fullmatch(raw) is not None
    sign = -1 if raw.startswith("-") else 1
    whole, _, fraction = raw.removeprefix("-").partition(".")
    assert len(fraction) <= scale
    return sign * (int(whole) * 10**scale + int(fraction.ljust(scale, "0")))


def test_tushare_daily_numeric_mapping_preserves_source_lexemes_and_exact_units() -> None:
    source = json.loads(SOURCE.read_text(), parse_float=str)
    fields = source["data"]["fields"]
    row = dict(zip(fields, source["data"]["items"][0], strict=True))
    assert {key: row[key] for key in EXPECTED["prices"]} == {
        key: EXPECTED["prices"][key]["raw"] for key in EXPECTED["prices"]
    }

    for key, value in EXPECTED["prices"].items():
        assert _units(row[key], value["scale"]) == value["units"]
    assert row["change"] == EXPECTED["change"]["raw"]
    assert row["pct_chg"] == EXPECTED["pct_change"]["raw"]
    assert _units(row["change"], 2) == EXPECTED["change"]["units"] == -18
    assert _units(row["pct_chg"], 4) == EXPECTED["pct_change"]["units"] == -19_169

    volume = EXPECTED["volume"]
    assert row["vol"] == volume["raw"]
    assert _units(row["vol"], volume["source_scale"]) == volume["source_units"]
    assert volume["source_units"] == volume["normalized_units"] == 115_836_645
    assert volume["lot_size_shares"] == 100
    assert volume["normalized_scale"] == 0

    amount = EXPECTED["amount"]
    assert row["amount"] == amount["raw"]
    assert _units(row["amount"], amount["source_scale"]) == amount["source_units"]
    assert amount["source_units"] == amount["normalized_units"] == 1_075_742_252
    assert amount["multiplier_to_CNY"] == 1000
    assert amount["normalized_scale"] == 0

    prices = EXPECTED["prices"]
    assert prices["low"]["units"] <= prices["open"]["units"] <= prices["high"]["units"]
    assert prices["low"]["units"] <= prices["close"]["units"] <= prices["high"]["units"]
    assert prices["close"]["units"] - prices["pre_close"]["units"] == EXPECTED[
        "change"
    ]["units"]

    assert "sha256:" + hashlib.sha256(SOURCE.read_bytes()).hexdigest() == EXPECTED[
        "source_daily_sha256"
    ]
    assert "sha256:" + hashlib.sha256(EVENT_TIME.read_bytes()).hexdigest() == EXPECTED[
        "event_time_fixture_sha256"
    ]
    canonical_body = {key: value for key, value in EXPECTED.items() if key != "mapping_hash"}
    assert canonical_sha256(canonical_body) == EXPECTED["mapping_hash"]
    assert "price_purpose" not in EXPECTED
    assert "market_event" not in EXPECTED
