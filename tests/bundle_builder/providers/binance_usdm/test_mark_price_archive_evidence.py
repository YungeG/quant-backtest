from __future__ import annotations

import csv
import hashlib
import io
import json
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)


FIXTURE = (
    Path(__file__).parents[3]
    / "fixtures/market_data/providers/binance_usdm/mark-price-klines-v1"
)
ARCHIVE = FIXTURE / "BTCUSDT-1m-2024-01-01.zip"
CHECKSUM = FIXTURE / "BTCUSDT-1m-2024-01-01.zip.CHECKSUM"
EXPECTED = FIXTURE / "evidence.expected.json"
CSV_HEADER = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "count",
    "taker_buy_volume",
    "taker_buy_quote_volume",
    "ignore",
]


def test_real_archive_has_exact_checksum_daily_closure_and_g12a_identity() -> None:
    expected = json.loads(EXPECTED.read_text())
    archive = ARCHIVE.read_bytes()
    checksum = CHECKSUM.read_bytes()
    archive_hash = hashlib.sha256(archive).hexdigest()

    assert checksum == f"{archive_hash}  {ARCHIVE.name}\n".encode()
    assert f"sha256:{archive_hash}" == expected["source_hashes"]["archive_sha256"]
    assert (
        "sha256:" + hashlib.sha256(checksum).hexdigest()
        == expected["source_hashes"]["checksum_sha256"]
    )

    with ZipFile(io.BytesIO(archive)) as zip_file:
        assert zip_file.namelist() == [expected["archive"]["member_name"]]
        csv_bytes = zip_file.read(zip_file.namelist()[0])
    assert (
        "sha256:" + hashlib.sha256(csv_bytes).hexdigest()
        == expected["source_hashes"]["csv_sha256"]
    )

    rows = list(csv.reader(io.StringIO(csv_bytes.decode("utf-8"), newline="")))
    assert rows[0] == CSV_HEADER
    assert len(rows[1:]) == 1440
    for index, row in enumerate(rows[1:]):
        open_time = 1_704_067_200_000 + index * 60_000
        assert int(row[0]) == open_time
        assert int(row[6]) == open_time + 59_999
        open_price, high, low, close = map(Decimal, row[1:5])
        assert low <= open_price <= high
        assert low <= close <= high

    acquired_at = expected["snapshot"]["members"][0][
        "acquired_at_epoch_nanoseconds"
    ]
    outcome = freeze_source_snapshot(
        members=(
            RawSourceMember(
                f"archive/{ARCHIVE.name}",
                archive,
                "0644",
                acquired_at,
                expected["source_hashes"]["archive_sha256"],
            ),
            RawSourceMember(
                f"archive/{CHECKSUM.name}",
                checksum,
                "0644",
                acquired_at,
                expected["source_hashes"]["checksum_sha256"],
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="binance.public_data",
            source_key=(
                "binance.public_data.futures.um.daily.mark_price_klines."
                "btcusdt.1m.2024-01-01"
            ),
            license_ref="binance.public_data.terms",
            retention_policy_ref="backtest.fixture.retention",
        ),
    )

    assert outcome.failure is None
    assert outcome.snapshot is not None
    assert outcome.snapshot.to_canonical_dict() == expected["snapshot"]
    assert outcome.snapshot.decision_grade_eligible is False
    assert outcome.snapshot.deployment_authorized is False
