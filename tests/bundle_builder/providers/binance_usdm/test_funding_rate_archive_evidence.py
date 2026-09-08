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
    / "fixtures/market_data/providers/binance_usdm/funding-rate-v1"
)
ARCHIVE = FIXTURE / "BTCUSDT-fundingRate-2020-01.zip"
CHECKSUM = FIXTURE / "BTCUSDT-fundingRate-2020-01.zip.CHECKSUM"
EXPECTED = json.loads((FIXTURE / "evidence.expected.json").read_text())


def test_real_funding_archive_has_exact_checksum_slots_and_g12a_identity() -> None:
    archive = ARCHIVE.read_bytes()
    checksum = CHECKSUM.read_bytes()
    archive_hash = hashlib.sha256(archive).hexdigest()
    assert checksum == f"{archive_hash}  {ARCHIVE.name}\n".encode()

    with ZipFile(io.BytesIO(archive)) as zip_file:
        assert zip_file.namelist() == [EXPECTED["archive"]["member_name"]]
        csv_bytes = zip_file.read(zip_file.namelist()[0])
    rows = list(csv.reader(io.StringIO(csv_bytes.decode(), newline="")))
    assert rows.pop(0) == ["calc_time", "funding_interval_hours", "last_funding_rate"]
    assert len(rows) == EXPECTED["archive"]["row_count"] == 93
    start = EXPECTED["archive"]["nominal_start_milliseconds"]
    assert all(
        int(row[0]) - (start + index * 28_800_000) in (0, 1, 2)
        for index, row in enumerate(rows)
    )
    assert all(row[1] == "8" for row in rows)
    assert any("E" in row[2] for row in rows)

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
            source_key="binance.public_data.futures.um.monthly.funding_rate.btcusdt.2020-01",
            license_ref="binance.public_data.terms",
            retention_policy_ref="backtest.fixture.retention",
        ),
    )
    assert outcome.failure is None
    assert outcome.snapshot is not None
    assert outcome.snapshot.to_canonical_dict() == EXPECTED["snapshot"]
    assert outcome.snapshot.decision_grade_eligible is False
    assert outcome.snapshot.deployment_authorized is False
