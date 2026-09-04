# IntradayData deterministic audit: blocked by concurrent mutation

## Status

**BLOCKED — no target-table query result was accepted.**

The requested target was:

```text
/srv/bcache-8t/ygguo/duckdb/quant-a50/quant_a50.duckdb
```

The audit required one immutable byte state, a read-only DuckDB connection, and a
stable pre/post database hash. Those prerequisites did not hold when the audit
started. The database was being modified by another process, its observed hash
changed, and DuckDB rejected the read-only connection because the writer held the
file lock. Per the read-only constraint, the audit did not copy, vacuum, alter,
attach, export, checkpoint, or otherwise modify the database. It did not terminate
or interfere with the writer.

## Frozen observations

All times are `+08:00` on 2026-08-18. Hash commands ran against the live path while
a writer existed, so the digests below are observations of attempted reads, not
authoritative snapshot identities.

| Observation time / time evidence | Size | SHA-256 / result | Meaning |
| --- | ---: | --- | --- |
| Immediately after target mtime `16:13:57.831570955` | 1,707,880,448 bytes | `3cea19103702959fc0bc74f5fe38b86805b456f901d3958ef82da38831109941` | First observed digest; not snapshot-authoritative because concurrent mutation was not yet excluded. |
| Immediately after target mtime `16:14:41.839827193` | 1,707,880,448 bytes | `8d72709d0d2d875d7a760bb9e5506d913180dbfd96bd57c9cddba28644b941c2` | Second observed digest differed despite unchanged file length, proving the target bytes were not stable. |
| `16:14:54` | 1,707,880,448 bytes | Writer still active | Confirms the instability was concurrent with the attempted audit. |

The non-sensitive process evidence at the lock failure was:

```text
PID 1255618
/home/ygguo/agent-projs/cycle-rotation-platform/venv/bin/python \
  -m operations.apps.import_to_duckdb --table market
```

The attempted connection used DuckDB's read-only API:

```python
duckdb.connect(
    "/srv/bcache-8t/ygguo/duckdb/quant-a50/quant_a50.duckdb",
    read_only=True,
)
```

DuckDB returned:

```text
IO Error: Could not set lock on file
"/srv/bcache-8t/ygguo/duckdb/quant-a50/quant_a50.duckdb":
Conflicting lock is held in /usr/bin/python3.13 (PID 1255618) by user ygguo.
```

No SQL statement was executed against `IntradayData`.

## Requested findings not claimed

Because no stable read-only target state was available, this report does **not**
claim or reproduce any of the following for the target bytes:

- the `IntradayData` schema, constraints, or natural key;
- total rows, duplicate rows, duplicate groups, or conflicting groups;
- exact duplicate rows versus conflicting value groups;
- symbol, date, time-bucket, frequency, or source concentration;
- conflict columns or numeric value-delta patterns;
- whether duplicate groups are identical imports, revisions, or incompatible
  observations.

The earlier counts in `docs/research/cross-project-market-data-inventory.md` are
prior inventory, not results of this run. They cannot be promoted to this audit
because the target is mutable and its observed bytes changed. No deduplication
winner is inferred.

## Query-definition status

No audit SQL is frozen here. Freezing column-level conflict queries before the
actual target schema is read would silently assume column names, types, null
semantics, and a natural key. That would not be a reproducible audit definition.
A tool was therefore not added: without an authoritative read-only open it could
only encode unverified assumptions or reproduce the same lock failure.

A resumed audit must freeze, in this order:

1. target path, byte size, mtime, DuckDB version, and pre-query SHA-256;
2. `pragma_table_info('IntradayData')`, table DDL, constraints, and indexes;
3. the natural key derived from confirmed table/provider semantics;
4. exact ordered SQL for row/group counts, exact-row equality, per-column conflict
   flags, value deltas, and symbol/date/time/frequency/source distributions;
5. post-query size, mtime, and SHA-256 equal to the pre-query observations;
6. a second execution whose canonical output hash equals the first.

## Exact unblock condition

Resume only after **the writer has stopped, two complete SHA-256 reads of the
unchanged target path are equal (with unchanged size and mtime), and a DuckDB
`read_only=True` connection opens successfully**. The pre-query hash must then
remain equal to a post-query hash. Until all of these checks hold in one audit
run, no deterministic `IntradayData` result is authoritative.
