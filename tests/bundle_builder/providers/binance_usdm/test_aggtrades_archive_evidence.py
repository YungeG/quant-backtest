from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile

from crypto_quant_bundle_builder import (
    RawSourceMember,
    SourceSnapshotProvenance,
    freeze_source_snapshot,
)


FIXTURE = (
    Path(__file__).parents[3]
    / "fixtures/market_data/providers/binance_usdm/aggtrades-v1"
)
ARCHIVE = FIXTURE / "BTCUSDT-aggTrades-2020-01-01.zip"
CHECKSUM = FIXTURE / "BTCUSDT-aggTrades-2020-01-01.zip.CHECKSUM"
EXPECTED = json.loads((FIXTURE / "evidence.expected.json").read_text())


def test_real_aggtrades_archive_has_exact_checksum_sequence_and_g12a_identity() -> None:
    archive = ARCHIVE.read_bytes()
    checksum = CHECKSUM.read_bytes()
    archive_hash = hashlib.sha256(archive).hexdigest()
    assert checksum == f"{archive_hash}  {ARCHIVE.name}\n".encode()

    with ZipFile(io.BytesIO(archive)) as zip_file:
        assert zip_file.namelist() == [EXPECTED["archive"]["member_name"]]
        csv_bytes = zip_file.read(zip_file.namelist()[0])
    rows = list(csv.reader(io.StringIO(csv_bytes.decode(), newline="")))
    assert len(rows) == EXPECTED["archive"]["row_count"] == 71_359
    first_id = EXPECTED["archive"]["first_aggregate_trade_id"]
    assert all(int(row[0]) == first_id + index for index, row in enumerate(rows))
    assert all(len(row) == 7 for row in rows)
    assert all(len(row[1].partition(".")[2]) <= 2 for row in rows)
    assert all(len(row[2].partition(".")[2]) <= 3 for row in rows)
    assert 1_577_836_800_000 <= int(rows[0][5])
    assert int(rows[-1][5]) < 1_577_923_200_000

    acquired_at = EXPECTED["snapshot"]["members"][0][
        "acquired_at_epoch_nanoseconds"
    ]
    outcome = freeze_source_snapshot(
        members=(
            RawSourceMember(
                f"archive/{ARCHIVE.name}",
                archive,
                "0644",
                acquired_at,
                EXPECTED["source_hashes"]["archive_sha256"],
            ),
            RawSourceMember(
                f"archive/{CHECKSUM.name}",
                checksum,
                "0644",
                acquired_at,
                EXPECTED["source_hashes"]["checksum_sha256"],
            ),
        ),
        provenance=SourceSnapshotProvenance(
            vendor_key="binance.public_data",
            source_key="binance.public_data.futures.um.daily.aggtrades.btcusdt.2020-01-01",
            license_ref="binance.public_data.terms",
            retention_policy_ref="backtest.fixture.retention",
        ),
    )
    assert outcome.failure is None
    assert outcome.snapshot is not None
    assert outcome.snapshot.to_canonical_dict() == EXPECTED["snapshot"]
    assert outcome.snapshot.decision_grade_eligible is False
    assert outcome.snapshot.deployment_authorized is False
