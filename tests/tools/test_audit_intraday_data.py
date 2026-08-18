from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest


duckdb = pytest.importorskip("duckdb")

TOOL = Path(__file__).parents[2] / "tools" / "audit_intraday_data.py"


def test_audit_is_read_only_and_deterministic_on_fixture(tmp_path: Path) -> None:
    database = tmp_path / "fixture.duckdb"
    connection = duckdb.connect(str(database))
    try:
        connection.execute(
            """
            CREATE TABLE IntradayData (
                ts_code VARCHAR NOT NULL,
                symbol VARCHAR NOT NULL,
                trading_day DATE NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                freq VARCHAR NOT NULL DEFAULT '5min',
                open DOUBLE,
                high DOUBLE,
                low DOUBLE,
                close DOUBLE,
                volume DOUBLE,
                amount DOUBLE,
                PRIMARY KEY(ts_code, timestamp, freq)
            );
            CREATE INDEX idx_intraday_symbol_day ON IntradayData(symbol, trading_day);
            INSERT INTO IntradayData VALUES
                ('000001.SZ', '000001', DATE '2026-01-05', TIMESTAMP '2026-01-05 09:35:00', '5min', 10, 11, 9, 10.5, 100, 1050),
                ('sz.000001', '000001', DATE '2026-01-05', TIMESTAMP '2026-01-05 09:35:00', '5min', 10, 11, 9, 10.5, 100, 1050),
                ('600000.SH', '600000', DATE '2026-01-05', TIMESTAMP '2026-01-05 09:40:00', '5min', 20, 21, 19, 20.5, 200, 4100),
                ('sh.600000', '600000', DATE '2026-01-05', TIMESTAMP '2026-01-05 09:40:00', '5min', 20, 21, 19, 20.6, 200, 4120),
                ('000002.SZ', '000002', DATE '2026-01-05', TIMESTAMP '2026-01-05 09:45:00', '5min', 30, 31, 29, 30.5, 300, 9150);
            """
        )
    finally:
        connection.close()

    before = hashlib.sha256(database.read_bytes()).hexdigest()
    first = subprocess.run(
        [sys.executable, str(TOOL), str(database)],
        check=True,
        capture_output=True,
    ).stdout
    second = subprocess.run(
        [sys.executable, str(TOOL), str(database)],
        check=True,
        capture_output=True,
    ).stdout

    assert first == second
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before
    payload = json.loads(first)
    summary = payload["results"]["duplicate_summary"][0]
    assert summary == {
        "conflicting_duplicate_group_count": 1,
        "distinct_natural_key_count": 3,
        "duplicate_excess_rows": 2,
        "duplicate_group_count": 2,
        "duplicate_symbol_count": 2,
        "duplicate_trading_day_count": 1,
        "maximum_group_size": 2,
        "nonduplicated_row_count": 1,
        "payload_exact_duplicate_group_count": 1,
        "physical_exact_duplicate_group_count": 0,
        "rows_in_duplicate_groups": 4,
        "total_rows": 5,
        "ts_code_conflict_group_count": 2,
    }
