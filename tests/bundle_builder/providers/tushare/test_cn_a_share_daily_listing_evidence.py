from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)


FIXTURE = (
    Path(__file__).parents[3]
    / "fixtures/market_data/providers/tushare/cn-a-share-daily-listing-v1"
)
DAILY = FIXTURE / "daily.json"
LISTING = FIXTURE / "stock-basic.json"
RECEIPT = FIXTURE / "acquisition-receipt.json"
EXPECTED = json.loads(
    (FIXTURE / "evidence.expected.json").read_text(), parse_float=Decimal
)


def _json(path: Path) -> object:
    return json.loads(path.read_text(), parse_float=Decimal)


def test_real_tushare_daily_listing_bytes_reproduce_g12a_and_duckdb_parity() -> None:
    daily_bytes = DAILY.read_bytes()
    listing_bytes = LISTING.read_bytes()
    receipt_bytes = RECEIPT.read_bytes()
    assert "sha256:" + hashlib.sha256(daily_bytes).hexdigest() == EXPECTED[
        "source_hashes"
    ]["daily_response_sha256"]
    assert "sha256:" + hashlib.sha256(listing_bytes).hexdigest() == EXPECTED[
        "source_hashes"
    ]["listing_response_sha256"]
    assert "sha256:" + hashlib.sha256(receipt_bytes).hexdigest() == EXPECTED[
        "source_hashes"
    ]["acquisition_receipt_sha256"]

    daily = _json(DAILY)
    listing = _json(LISTING)
    receipt = _json(RECEIPT)
    assert isinstance(daily, dict) and isinstance(listing, dict)
    assert daily["data"]["fields"] == EXPECTED["provider_evidence"]["daily_fields"]
    assert daily["data"]["items"] == [EXPECTED["provider_evidence"]["daily_row"]]
    assert listing["data"]["fields"] == EXPECTED["provider_evidence"]["listing_fields"]
    assert listing["data"]["items"] == [EXPECTED["provider_evidence"]["listing_row"]]
    assert "token" not in receipt
    assert "TUSHARE_TOKEN" not in receipt_bytes.decode()

    acquired_at = EXPECTED["snapshot"]["members"][0][
        "acquired_at_epoch_nanoseconds"
    ]
    outcome = freeze_source_snapshot(
        members=(
            RawSourceMember(
                "response/daily.json",
                daily_bytes,
                "0644",
                acquired_at,
                None,
            ),
            RawSourceMember(
                "response/stock-basic.json",
                listing_bytes,
                "0644",
                acquired_at,
                None,
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="tushare.pro",
            source_key="tushare.pro.daily_listing.000001.sz.20240102",
            license_ref="tushare.pro.terms",
            retention_policy_ref="backtest.acquisition.candidate",
        ),
    )
    assert outcome.failure is None
    assert outcome.snapshot is not None
    assert outcome.snapshot.to_canonical_dict() == EXPECTED["snapshot"]

    fields = daily["data"]["fields"]
    row = dict(zip(fields, daily["data"]["items"][0], strict=True))
    backup = EXPECTED["duckdb_backup_parity"]["market_row"]
    assert row["trade_date"] == backup[0].replace("-", "")
    assert row["ts_code"][:6] == backup[1]
    assert [row[key] for key in ("open", "high", "low", "close")] == backup[3:7]
    assert row["vol"] * 100 == backup[7]
    assert row["amount"] * 1000 == backup[8]
    assert row["pct_chg"] == backup[9]

    listing_fields = listing["data"]["fields"]
    listing_row = dict(
        zip(listing_fields, listing["data"]["items"][0], strict=True)
    )
    static = EXPECTED["duckdb_backup_parity"]["static_row"]
    assert [
        listing_row["symbol"],
        listing_row["ts_code"],
        listing_row["name"],
        listing_row["area"],
        listing_row["industry"],
        listing_row["market"],
    ] == static[:6]
    assert listing_row["list_date"] == static[6].replace("-", "")
    assert receipt["decision_grade_eligible"] is False
    assert receipt["deployment_authorized"] is False
