#!/usr/bin/env python3
"""Deterministic, read-only audit of the external IntradayData table."""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import decimal
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

EXPECTED_COLUMNS = [
    (0, "ts_code", "VARCHAR", True, None, True),
    (1, "symbol", "VARCHAR", True, None, False),
    (2, "trading_day", "DATE", True, None, False),
    (3, "timestamp", "TIMESTAMP", True, None, True),
    (4, "freq", "VARCHAR", True, "'5min'", True),
    (5, "open", "DOUBLE", False, None, False),
    (6, "high", "DOUBLE", False, None, False),
    (7, "low", "DOUBLE", False, None, False),
    (8, "close", "DOUBLE", False, None, False),
    (9, "volume", "DOUBLE", False, None, False),
    (10, "amount", "DOUBLE", False, None, False),
]

DUPLICATE_GROUPS_CTE = """duplicate_groups AS (
    SELECT
        symbol,
        timestamp,
        freq,
        count(*) AS row_count,
        count(DISTINCT struct_pack(v := ts_code)) AS ts_code_values,
        count(DISTINCT struct_pack(v := trading_day)) AS trading_day_values,
        count(DISTINCT struct_pack(v := open)) AS open_values,
        count(DISTINCT struct_pack(v := high)) AS high_values,
        count(DISTINCT struct_pack(v := low)) AS low_values,
        count(DISTINCT struct_pack(v := close)) AS close_values,
        count(DISTINCT struct_pack(v := volume)) AS volume_values,
        count(DISTINCT struct_pack(v := amount)) AS amount_values
    FROM IntradayData
    GROUP BY symbol, timestamp, freq
    HAVING count(*) > 1
)"""

SQL_QUERIES: list[tuple[str, str]] = [
    ("duckdb_version", "SELECT version() AS version"),
    (
        "table_info",
        "SELECT * FROM pragma_table_info('IntradayData') ORDER BY cid",
    ),
    (
        "ddl",
        """SELECT sql
FROM duckdb_tables()
WHERE database_name = current_database()
  AND schema_name = 'main'
  AND table_name = 'IntradayData'
ORDER BY table_name""",
    ),
    (
        "constraints",
        """SELECT constraint_index, constraint_type, constraint_text,
       constraint_column_indexes, constraint_column_names, constraint_name
FROM duckdb_constraints()
WHERE database_name = current_database()
  AND schema_name = 'main'
  AND table_name = 'IntradayData'
ORDER BY constraint_index""",
    ),
    (
        "indexes",
        """SELECT index_name, is_unique, is_primary, expressions, sql
FROM duckdb_indexes()
WHERE database_name = current_database()
  AND schema_name = 'main'
  AND table_name = 'IntradayData'
ORDER BY index_name""",
    ),
    (
        "coverage",
        """SELECT
    count(*) AS total_rows,
    count(DISTINCT symbol) AS symbol_count,
    count(DISTINCT trading_day) AS trading_day_count,
    min(trading_day) AS trading_day_min,
    max(trading_day) AS trading_day_max,
    min(timestamp) AS timestamp_min,
    max(timestamp) AS timestamp_max,
    count(*) FILTER (WHERE trading_day <> CAST(timestamp AS DATE)) AS trading_day_timestamp_mismatch_rows,
    count(*) FILTER (
        WHERE symbol <> CASE
            WHEN regexp_matches(ts_code, '^[0-9]{6}\\.(SH|SZ|BJ)$') THEN left(ts_code, 6)
            WHEN regexp_matches(ts_code, '^(sh|sz|bj)\\.[0-9]{6}$') THEN right(ts_code, 6)
            ELSE symbol
        END
    ) AS symbol_ts_code_mismatch_rows
FROM IntradayData""",
    ),
    (
        "duplicate_summary",
        f"""WITH {DUPLICATE_GROUPS_CTE},
physical_duplicates AS (
    SELECT count(*) AS row_count
    FROM IntradayData
    GROUP BY ts_code, symbol, trading_day, timestamp, freq,
             open, high, low, close, volume, amount
    HAVING count(*) > 1
)
SELECT
    (SELECT count(*) FROM IntradayData) AS total_rows,
    (SELECT count(*) FROM IntradayData) - (SELECT coalesce(sum(row_count - 1), 0) FROM duplicate_groups) AS distinct_natural_key_count,
    (SELECT count(*) FROM duplicate_groups) AS duplicate_group_count,
    (SELECT count(DISTINCT symbol) FROM duplicate_groups) AS duplicate_symbol_count,
    (SELECT count(DISTINCT CAST(timestamp AS DATE)) FROM duplicate_groups) AS duplicate_trading_day_count,
    (SELECT coalesce(sum(row_count), 0) FROM duplicate_groups) AS rows_in_duplicate_groups,
    (SELECT count(*) FROM IntradayData) - (SELECT coalesce(sum(row_count), 0) FROM duplicate_groups) AS nonduplicated_row_count,
    (SELECT coalesce(sum(row_count - 1), 0) FROM duplicate_groups) AS duplicate_excess_rows,
    (SELECT coalesce(max(row_count), 1) FROM duplicate_groups) AS maximum_group_size,
    (SELECT count(*) FROM physical_duplicates) AS physical_exact_duplicate_group_count,
    count(*) FILTER (
        WHERE greatest(trading_day_values, open_values, high_values, low_values,
                       close_values, volume_values, amount_values) = 1
    ) AS payload_exact_duplicate_group_count,
    count(*) FILTER (
        WHERE greatest(trading_day_values, open_values, high_values, low_values,
                       close_values, volume_values, amount_values) > 1
    ) AS conflicting_duplicate_group_count,
    count(*) FILTER (WHERE ts_code_values > 1) AS ts_code_conflict_group_count
FROM duplicate_groups""",
    ),
    (
        "per_column_conflicts",
        f"""WITH {DUPLICATE_GROUPS_CTE}
SELECT column_order, column_name, conflict_groups
FROM (
    SELECT 0 AS column_order, 'ts_code' AS column_name, count(*) FILTER (WHERE ts_code_values > 1) AS conflict_groups FROM duplicate_groups
    UNION ALL SELECT 1, 'trading_day', count(*) FILTER (WHERE trading_day_values > 1) FROM duplicate_groups
    UNION ALL SELECT 2, 'open', count(*) FILTER (WHERE open_values > 1) FROM duplicate_groups
    UNION ALL SELECT 3, 'high', count(*) FILTER (WHERE high_values > 1) FROM duplicate_groups
    UNION ALL SELECT 4, 'low', count(*) FILTER (WHERE low_values > 1) FROM duplicate_groups
    UNION ALL SELECT 5, 'close', count(*) FILTER (WHERE close_values > 1) FROM duplicate_groups
    UNION ALL SELECT 6, 'volume', count(*) FILTER (WHERE volume_values > 1) FROM duplicate_groups
    UNION ALL SELECT 7, 'amount', count(*) FILTER (WHERE amount_values > 1) FROM duplicate_groups
)
ORDER BY column_order""",
    ),
    (
        "numeric_delta_summaries",
        """WITH grouped AS (
    SELECT symbol, timestamp, freq, count(*) AS row_count,
           count(DISTINCT struct_pack(v := open)) AS open_values,
           count(DISTINCT struct_pack(v := high)) AS high_values,
           count(DISTINCT struct_pack(v := low)) AS low_values,
           count(DISTINCT struct_pack(v := close)) AS close_values,
           count(DISTINCT struct_pack(v := volume)) AS volume_values,
           count(DISTINCT struct_pack(v := amount)) AS amount_values,
           count(*) FILTER (WHERE open IS NULL) AS open_nulls, max(open) - min(open) AS open_delta,
           count(*) FILTER (WHERE high IS NULL) AS high_nulls, max(high) - min(high) AS high_delta,
           count(*) FILTER (WHERE low IS NULL) AS low_nulls, max(low) - min(low) AS low_delta,
           count(*) FILTER (WHERE close IS NULL) AS close_nulls, max(close) - min(close) AS close_delta,
           count(*) FILTER (WHERE volume IS NULL) AS volume_nulls, max(volume) - min(volume) AS volume_delta,
           count(*) FILTER (WHERE amount IS NULL) AS amount_nulls, max(amount) - min(amount) AS amount_delta
    FROM IntradayData
    GROUP BY symbol, timestamp, freq
    HAVING count(*) > 1
), deltas AS (
    SELECT 0 AS column_order, 'open' AS column_name, row_count, open_values AS value_count, open_nulls AS null_count, open_delta AS delta FROM grouped
    UNION ALL SELECT 1, 'high', row_count, high_values, high_nulls, high_delta FROM grouped
    UNION ALL SELECT 2, 'low', row_count, low_values, low_nulls, low_delta FROM grouped
    UNION ALL SELECT 3, 'close', row_count, close_values, close_nulls, close_delta FROM grouped
    UNION ALL SELECT 4, 'volume', row_count, volume_values, volume_nulls, volume_delta FROM grouped
    UNION ALL SELECT 5, 'amount', row_count, amount_values, amount_nulls, amount_delta FROM grouped
)
SELECT column_order, column_name,
       count(*) FILTER (WHERE value_count > 1) AS conflicting_groups,
       count(*) FILTER (WHERE value_count > 1 AND null_count > 0) AS conflicting_groups_with_null,
       min(delta) FILTER (WHERE value_count > 1) AS minimum_delta,
       avg(delta) FILTER (WHERE value_count > 1) AS average_delta,
       quantile_cont(delta, 0.5) FILTER (WHERE value_count > 1) AS median_delta,
       quantile_cont(delta, 0.95) FILTER (WHERE value_count > 1) AS p95_delta,
       max(delta) FILTER (WHERE value_count > 1) AS maximum_delta
FROM deltas
GROUP BY column_order, column_name
ORDER BY column_order""",
    ),
    (
        "group_size_distribution",
        """SELECT row_count AS group_size, count(*) AS duplicate_groups
FROM (
    SELECT symbol, timestamp, freq, count(*) AS row_count
    FROM IntradayData
    GROUP BY symbol, timestamp, freq
    HAVING count(*) > 1
)
GROUP BY row_count
ORDER BY row_count""",
    ),
    (
        "frequency_distribution",
        """WITH keyed AS (
    SELECT *, count(*) OVER (PARTITION BY symbol, timestamp, freq) AS natural_key_rows
    FROM IntradayData
)
SELECT freq, count(*) AS rows,
       count(*) FILTER (WHERE natural_key_rows > 1) AS rows_in_duplicate_groups,
       count(DISTINCT struct_pack(sym := symbol, ts := timestamp, frequency := freq))
           FILTER (WHERE natural_key_rows > 1) AS duplicate_groups
FROM keyed
GROUP BY freq
ORDER BY freq""",
    ),
    (
        "ts_code_format_distribution",
        """WITH keyed AS (
    SELECT *, count(*) OVER (PARTITION BY symbol, timestamp, freq) AS natural_key_rows
    FROM IntradayData
), classified AS (
    SELECT *, CASE
        WHEN regexp_matches(ts_code, '^[0-9]{6}\\.(SH|SZ|BJ)$') THEN 'suffix_upper'
        WHEN regexp_matches(ts_code, '^(sh|sz|bj)\\.[0-9]{6}$') THEN 'prefix_lower'
        ELSE 'other'
    END AS ts_code_format
    FROM keyed
)
SELECT ts_code_format, count(*) AS rows,
       count(*) FILTER (WHERE natural_key_rows > 1) AS rows_in_duplicate_groups,
       count(DISTINCT symbol) AS symbols
FROM classified
GROUP BY ts_code_format
ORDER BY ts_code_format""",
    ),
    (
        "duplicate_ts_code_format_pairs",
        """WITH classified AS (
    SELECT symbol, timestamp, freq, CASE
        WHEN regexp_matches(ts_code, '^[0-9]{6}\\.(SH|SZ|BJ)$') THEN 'suffix_upper'
        WHEN regexp_matches(ts_code, '^(sh|sz|bj)\\.[0-9]{6}$') THEN 'prefix_lower'
        ELSE 'other'
    END AS ts_code_format
    FROM IntradayData
), duplicate_groups AS (
    SELECT symbol, timestamp, freq,
           string_agg(ts_code_format, '+' ORDER BY ts_code_format) AS format_pair
    FROM classified
    GROUP BY symbol, timestamp, freq
    HAVING count(*) > 1
)
SELECT format_pair, count(*) AS duplicate_groups
FROM duplicate_groups
GROUP BY format_pair
ORDER BY format_pair""",
    ),
    (
        "duplicate_symbol_distribution",
        f"""WITH {DUPLICATE_GROUPS_CTE}
SELECT symbol,
       count(*) AS duplicate_groups,
       sum(row_count) AS rows_in_duplicate_groups,
       count(*) FILTER (
           WHERE greatest(trading_day_values, open_values, high_values, low_values,
                          close_values, volume_values, amount_values) = 1
       ) AS payload_exact_groups,
       count(*) FILTER (
           WHERE greatest(trading_day_values, open_values, high_values, low_values,
                          close_values, volume_values, amount_values) > 1
       ) AS conflicting_groups
FROM duplicate_groups
GROUP BY symbol
ORDER BY duplicate_groups DESC, symbol
LIMIT 25""",
    ),
    (
        "duplicate_month_distribution",
        f"""WITH {DUPLICATE_GROUPS_CTE}
SELECT strftime(timestamp, '%Y-%m') AS month,
       count(*) AS duplicate_groups,
       sum(row_count) AS rows_in_duplicate_groups,
       count(*) FILTER (
           WHERE greatest(trading_day_values, open_values, high_values, low_values,
                          close_values, volume_values, amount_values) = 1
       ) AS payload_exact_groups,
       count(*) FILTER (
           WHERE greatest(trading_day_values, open_values, high_values, low_values,
                          close_values, volume_values, amount_values) > 1
       ) AS conflicting_groups
FROM duplicate_groups
GROUP BY month
ORDER BY month""",
    ),
    (
        "duplicate_time_distribution",
        f"""WITH {DUPLICATE_GROUPS_CTE}
SELECT strftime(timestamp, '%H:%M:%S') AS bar_time,
       count(*) AS duplicate_groups,
       sum(row_count) AS rows_in_duplicate_groups,
       count(*) FILTER (
           WHERE greatest(trading_day_values, open_values, high_values, low_values,
                          close_values, volume_values, amount_values) = 1
       ) AS payload_exact_groups,
       count(*) FILTER (
           WHERE greatest(trading_day_values, open_values, high_values, low_values,
                          close_values, volume_values, amount_values) > 1
       ) AS conflicting_groups
FROM duplicate_groups
GROUP BY bar_time
ORDER BY bar_time""",
    ),
]


@dataclasses.dataclass(frozen=True)
class FileState:
    size: int
    mtime_ns: int
    inode: int
    sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stat_tuple(path: Path) -> tuple[int, int, int]:
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, stat.st_ino


def stable_pre_query_state(path: Path) -> FileState:
    before = stat_tuple(path)
    first_hash = sha256_file(path)
    middle = stat_tuple(path)
    second_hash = sha256_file(path)
    after = stat_tuple(path)
    if before != middle or middle != after or first_hash != second_hash:
        raise RuntimeError("database bytes were not stable across two complete pre-query SHA-256 reads")
    return FileState(*after, sha256=second_hash)


def post_query_state(path: Path, expected: FileState) -> FileState:
    before = stat_tuple(path)
    digest = sha256_file(path)
    after = stat_tuple(path)
    observed = FileState(*after, sha256=digest)
    if before != after or observed != expected:
        raise RuntimeError("database size, mtime, inode, or SHA-256 changed during the audit")
    return observed


def json_value(value: Any) -> Any:
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat(sep=" ") if isinstance(value, dt.datetime) else value.isoformat()
    if isinstance(value, decimal.Decimal):
        return format(value, "f")
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, tuple):
        return [json_value(item) for item in value]
    if isinstance(value, list):
        return [json_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    return value


def query_rows(connection: Any, sql: str) -> list[dict[str, Any]]:
    if sql not in {statement for _, statement in SQL_QUERIES}:
        raise ValueError("SQL statement is not in the frozen audit allowlist")
    relation = connection.sql(sql)
    columns = relation.columns
    return [
        {column: json_value(value) for column, value in zip(columns, row, strict=True)}
        for row in relation.fetchall()
    ]


def audit(path: Path) -> dict[str, Any]:
    import duckdb

    resolved = path.expanduser().resolve(strict=True)
    pre = stable_pre_query_state(resolved)
    connection = duckdb.connect(str(resolved), read_only=True, config={"threads": "1"})
    try:
        results: dict[str, list[dict[str, Any]]] = {}
        for name, sql in SQL_QUERIES:
            results[name] = query_rows(connection, sql)
        actual_columns = [
            (
                row["cid"],
                row["name"],
                row["type"],
                row["notnull"],
                row["dflt_value"],
                row["pk"],
            )
            for row in results["table_info"]
        ]
        if actual_columns != EXPECTED_COLUMNS:
            raise RuntimeError(f"unexpected IntradayData schema: {actual_columns!r}")
    finally:
        connection.close()
    post = post_query_state(resolved, pre)
    return {
        "audit_schema_version": 1,
        "target": {
            "path": str(resolved),
            "size": pre.size,
            "mtime_ns": pre.mtime_ns,
            "inode": pre.inode,
            "sha256_pre_read_1": pre.sha256,
            "sha256_pre_read_2": pre.sha256,
            "sha256_post": post.sha256,
            "unchanged": pre == post,
        },
        "connection": {"read_only": True, "threads": 1, "duckdb_python_version": duckdb.__version__},
        "natural_key": {
            "columns": ["symbol", "timestamp", "freq"],
            "basis": "canonical symbol plus bar timestamp and frequency in all three source importers; ts_code formatting differs by importer",
        },
        "source_attribution": {
            "source_column_present": False,
            "ts_code_format_is_proxy_not_proof": True,
            "known_importer_formats": {
                "prefix_lower": "AkShare importer-compatible: sh.600000 / sz.000001 / bj.430047",
                "suffix_upper": "Tushare- and Baostock-importer-compatible: 600000.SH / 000001.SZ / 430047.BJ",
            },
        },
        "query_order": [name for name, _ in SQL_QUERIES],
        "sql": [{"name": name, "statement": sql} for name, sql in SQL_QUERIES],
        "results": results,
    }


def canonical_bytes(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path)
    args = parser.parse_args()
    os.write(1, canonical_bytes(audit(args.database)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
