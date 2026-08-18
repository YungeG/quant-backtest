# IntradayData deterministic read-only audit — 2026-08-18

## Status

**PASSED — the deterministic read-only audit completed against one unchanged target byte state.**

This status means the audit was reproducible and the target remained unchanged. It
does **not** mean `IntradayData` is duplicate-free or acceptance-ready. The audit
found 14,496 duplicate natural-key groups, including 13,356 groups with conflicting
bar payloads.

## Frozen artifacts and identities

| Item | Frozen value |
| --- | --- |
| Target | `/srv/bcache-8t/ygguo/duckdb/quant-a50/quant_a50.duckdb` |
| Target size | 1,708,404,736 bytes |
| Target mtime | `2026-08-18 17:18:53.950034884 +0800` (`1787044733950034884` ns since epoch) |
| Target inode | `108270713` |
| Pre-query SHA-256 read 1 | `7d82c0408f09ef665ea93a718def3e5355920eca703ad4d145217e23c39992ef` |
| Pre-query SHA-256 read 2 | `7d82c0408f09ef665ea93a718def3e5355920eca703ad4d145217e23c39992ef` |
| Post-query SHA-256 | `7d82c0408f09ef665ea93a718def3e5355920eca703ad4d145217e23c39992ef` |
| DuckDB Python / SQL version | `1.5.1` / `v1.5.1` |
| Locked audit dependency | dev-only `duckdb==1.5.1` in `pyproject.toml` and `uv.lock` |
| Canonical audit JSON | `docs/research/intraday-data-deterministic-audit-20260818.json` |
| Canonical audit SHA-256, both exact locked runs | `4224e9ffcebde23c116107d091b40620620c4a6b828dee0b2e94eb64db9458cf` |
| Audit tool | `tools/audit_intraday_data.py` |

`lsof` reported no open target handle immediately before the initial two full
hash reads, immediately after those reads, immediately before the two final audit
runs, and immediately after them. A `duckdb.connect(path, read_only=True,
config={"threads": "1"})` connection opened successfully. No external process was
terminated, waited on, signalled, or controlled.

Each exact audit run independently performed two equal full pre-query SHA-256
reads with stable size/mtime/inode, opened only a read-only single-threaded DuckDB
connection, executed the same 16 ordered queries, closed the connection, and
required a full post-query hash and stat equal to the pre-query state. The two
canonical JSON files were byte-identical.

## Inputs reviewed

The audit used the prior blocked report and cross-project inventory in this
repository, then confirmed semantics from exact `git show` bytes at
`cycle-rotation-platform` commit
`91cd8e182b736a07319e0f504e64572b32ea7dea`:

| Source | SHA-256 |
| --- | --- |
| `docs/research/intraday-data-deterministic-audit-blocked-20260818.md` | `a85334a818963e66cf5b535db7aea2b2013c1145eaac579deafa44d2d34e464a` |
| `docs/research/cross-project-market-data-inventory.md` | `dc7348bfb374fbc63bdaf7aa754ea50dbb4495edf571bd7a69e01781c8d0d89d` |
| `cycle-rotation-platform/core/intraday.py` | `836ed999480c678be4bcf7d73deb53267759847b8ab26e668aadba430aba9f81` |
| `operations/apps/fetch_intraday_tushare.py` | `851adf045945c67ebfd7a421ba8bccf8050652138fd899e3db2d78c01edc5648` |
| `operations/apps/fetch_intraday_akshare.py` | `8e481d92f94ad44ba37d4a5c4847192041e39a17034267a918cc1f5f6093fb05` |
| `operations/apps/fetch_intraday_baostock.py` | `af9eea685d4812d33ef35faa3e60a228b46fdb6563bdcdbb90b081008d126ec2` |
| `docs/intraday-data-architecture-2026-04-22.md` | `524cf2bcb4f7f0e3a2142d72fd56a7086649b0d5c414d0d45a7ac2106ada2a5c` |

The Baostock working tree was dirty when rechecked. Its observed uncommitted file
hash was `c2c2ded9af8fcc81e803a8cc63b46b7681e5c022d18d323291f17290437dfd1e`.
That hash is non-authoritative, is explicitly excluded from the semantic input
identity, and is not attributed to the commit above.

All three committed importers canonicalize `symbol` to six digits and identify a bar by its
symbol, timestamp, and frequency. Consumers query by `symbol`, `trading_day`, and
`freq`, ordered by timestamp. The importers do not use one canonical `ts_code`
representation: AkShare writes lower-case exchange prefixes such as `sh.600000`,
while Tushare and Baostock write upper-case suffixes such as `600000.SH`.

## Frozen schema

`pragma_table_info('IntradayData')` returned:

| cid | name | type | not null | default | PK member |
| ---: | --- | --- | --- | --- | --- |
| 0 | `ts_code` | `VARCHAR` | yes | null | yes |
| 1 | `symbol` | `VARCHAR` | yes | null | no |
| 2 | `trading_day` | `DATE` | yes | null | no |
| 3 | `timestamp` | `TIMESTAMP` | yes | null | yes |
| 4 | `freq` | `VARCHAR` | yes | `'5min'` | yes |
| 5 | `open` | `DOUBLE` | no | null | no |
| 6 | `high` | `DOUBLE` | no | null | no |
| 7 | `low` | `DOUBLE` | no | null | no |
| 8 | `close` | `DOUBLE` | no | null | no |
| 9 | `volume` | `DOUBLE` | no | null | no |
| 10 | `amount` | `DOUBLE` | no | null | no |

Frozen DDL:

```sql
CREATE TABLE IntradayData(ts_code VARCHAR, symbol VARCHAR NOT NULL, trading_day DATE NOT NULL, "timestamp" TIMESTAMP, freq VARCHAR DEFAULT('5min'), open DOUBLE, high DOUBLE, low DOUBLE, "close" DOUBLE, volume DOUBLE, amount DOUBLE, PRIMARY KEY(ts_code, "timestamp", freq));
```

Frozen constraints are NOT NULL constraints on `ts_code`, `symbol`,
`trading_day`, `timestamp`, and `freq`, plus primary key
`(ts_code, timestamp, freq)`. The only catalogued secondary index is:

```sql
CREATE INDEX idx_intraday_symbol_day ON IntradayData(symbol, trading_day);
```

## Natural key and classification

The confirmed observation natural key is **`(symbol, timestamp, freq)`**. This is
not the physical primary key. It follows the shared normalized provider semantics:
a canonical security symbol, one bar timestamp, and one frequency identify the
same historical bar. `trading_day` is redundant with the timestamp date in all
3,513,072 rows. `ts_code` is an exchange-qualified representation whose format
varies by importer and therefore cannot distinguish two observations for the same
bar.

Duplicate groups are classified as follows:

- **physical exact duplicate:** every stored column is equal;
- **payload exact duplicate:** the natural key and `trading_day`/OHLCVA payload
  are equal, but representational `ts_code` may differ;
- **conflicting duplicate:** at least one of `trading_day`, OHLC, volume, or
  amount differs within the natural-key group.

This classification does not select a source or winner.

## Findings

### Coverage and duplicate counts

| Metric | Count |
| --- | ---: |
| Total rows | 3,513,072 |
| Distinct natural keys | 3,498,576 |
| Nonduplicated rows | 3,484,080 |
| Duplicate natural-key groups | 14,496 |
| Rows in duplicate groups | 28,992 |
| Duplicate excess rows | 14,496 |
| Maximum group size | 2 |
| Symbols with duplicate groups | 12 |
| Trading days with duplicate groups | 27 |
| Physical exact duplicate groups | 0 |
| Payload exact duplicate groups | 1,140 |
| Conflicting duplicate groups | 13,356 |
| Groups with differing `ts_code` | 14,496 |

Coverage is 2,065 symbols and 1,377 trading days, from `2020-01-13 09:35:00`
through `2026-04-20 15:00:00`. No row has a `trading_day`/timestamp-date mismatch
or a canonical symbol/`ts_code` symbol mismatch.

### Per-column conflicting groups

| Column | Conflicting groups |
| --- | ---: |
| `ts_code` | 14,496 |
| `trading_day` | 0 |
| `open` | 5,215 |
| `high` | 3,198 |
| `low` | 3,192 |
| `close` | 2,392 |
| `volume` | 8,235 |
| `amount` | 12,513 |

Column conflict counts overlap; they must not be summed as independent groups.

### Numeric absolute range within conflicting groups

Each duplicate group has two rows, so each range is the absolute two-row delta.
No conflicting numeric group contains a null.

| Column | Groups | Minimum | Average | Median | P95 | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `open` | 5,215 | 0.00999999999999801 | 0.011877277085329865 | 0.009999999999999787 | 0.02000000000000135 | 0.10000000000000142 |
| `high` | 3,198 | 0.00999999999999801 | 0.013667917448404577 | 0.009999999999999787 | 0.030000000000001137 | 0.23999999999999844 |
| `low` | 3,192 | 0.00999999999999801 | 0.013743734335838923 | 0.009999999999999787 | 0.030000000000001137 | 0.21000000000000085 |
| `close` | 2,392 | 0.00999999999999801 | 0.011973244147156819 | 0.009999999999999787 | 0.02000000000000135 | 0.08000000000000007 |
| `volume` | 8,235 | 14.0 | 6969.105768063145 | 1400.0 | 28500.0 | 964100.0 |
| `amount` | 12,513 | 0.00009999796748161316 | 59313.455772780464 | 5131.9646000005305 | 243881.96835999988 | 17623746.971199997 |

The binary-float spellings above are preserved exactly from DuckDB/Python in the
canonical output; no decimal precision or provider unit semantics are inferred.

### Distributions explaining the overlap

All 3,513,072 rows have frequency `5min`. All 14,496 duplicate groups pair exactly
one `prefix_lower` `ts_code` row with one `suffix_upper` row:

| `ts_code` format | All rows | Rows in duplicate groups | Symbols |
| --- | ---: | ---: | ---: |
| `prefix_lower` | 96,238 | 14,496 | 77 |
| `suffix_upper` | 3,416,834 | 14,496 | 2,022 |

The format pair is consistent with overlap between AkShare-formatted rows and
Tushare/Baostock-formatted rows, but the table has no source column, so format is
only a proxy and cannot prove which importer or provider produced a row.

Duplicates are confined to March and April 2026:

| Month | Duplicate groups | Payload exact | Conflicting |
| --- | ---: | ---: | ---: |
| `2026-03` | 8,160 | 564 | 7,596 |
| `2026-04` | 6,336 | 576 | 5,760 |

All 48 normal five-minute bar times from `09:35:00` through `15:00:00` are
represented. Every bar time has exactly 302 duplicate groups / 604 rows, so the
overlap is full-session rather than concentrated at a particular time.

All affected symbols are listed below; the 25-row query limit did not truncate
because only 12 symbols are affected:

| Symbol | Duplicate groups | Payload exact | Conflicting |
| --- | ---: | ---: | ---: |
| `000600` | 1,296 | 49 | 1,247 |
| `000722` | 1,296 | 215 | 1,081 |
| `000791` | 1,296 | 195 | 1,101 |
| `000899` | 1,296 | 109 | 1,187 |
| `000993` | 1,296 | 146 | 1,150 |
| `001286` | 1,296 | 42 | 1,254 |
| `001896` | 1,296 | 5 | 1,291 |
| `600292` | 1,296 | 152 | 1,144 |
| `600452` | 1,296 | 7 | 1,289 |
| `600505` | 1,296 | 159 | 1,137 |
| `600644` | 1,296 | 31 | 1,265 |
| `601139` | 240 | 30 | 210 |

The complete ordered time distribution, exact schema rows, constraints, indexes,
all SQL text, and every result row are frozen in the canonical JSON.

## Exact ordered SQL and commands

The canonical JSON contains the exact SQL text in `sql` and this fixed execution
order in `query_order`:

1. `duckdb_version`
2. `table_info`
3. `ddl`
4. `constraints`
5. `indexes`
6. `coverage`
7. `duplicate_summary`
8. `per_column_conflicts`
9. `numeric_delta_summaries`
10. `group_size_distribution`
11. `frequency_distribution`
12. `ts_code_format_distribution`
13. `duplicate_ts_code_format_pairs`
14. `duplicate_symbol_distribution`
15. `duplicate_month_distribution`
16. `duplicate_time_distribution`

Final reproducibility commands:

```bash
DB=/srv/bcache-8t/ygguo/duckdb/quant-a50/quant_a50.duckdb

lsof "$DB"
stat --format='%s|%Y|%y|%i' "$DB"
sha256sum "$DB"
stat --format='%s|%Y|%y|%i' "$DB"
sha256sum "$DB"
stat --format='%s|%Y|%y|%i' "$DB"

uv run --locked pytest -q tests/tools/test_audit_intraday_data.py
uv run --locked python tools/audit_intraday_data.py "$DB" > /tmp/intraday-audit-run1.json
uv run --locked python tools/audit_intraday_data.py "$DB" > /tmp/intraday-audit-run2.json
sha256sum /tmp/intraday-audit-run1.json /tmp/intraday-audit-run2.json
cmp -s /tmp/intraday-audit-run1.json /tmp/intraday-audit-run2.json
lsof "$DB"
sha256sum "$DB"
```

The locked dev environment pins exactly `duckdb==1.5.1`; the tool also rejects a
different Python or SQL DuckDB version. It uses only
`duckdb.connect(path, read_only=True, config={"threads": "1"})` for the audited
database. The committed test creates and writes only a temporary fixture, closes
it, and then invokes the audit twice against that fixture. Normal locked CI imports
DuckDB directly and executes this test; it cannot skip for a missing dependency.

## Limitations and explicit non-claims

- No row winner, preferred provider, source priority, or deduplication policy is
  inferred. The evidence supports describing conflicts, not resolving them.
- `ts_code` format is not source provenance. Tushare and Baostock share the same
  suffix format, and a row could have been produced by other code.
- The table retains no fetch time, provider response identity, correction chain,
  raw payload hash, or explicit source column. The audit cannot identify which
  value is newer or authoritative.
- Numeric deltas are stored-value differences only. They are not interpreted as
  corrections, rounding, unit conversion, adjustment, or provider error.
- `lsof`, stat, and hashes are observational checks. They cannot prove that no
  process briefly opened and closed the path between checks. DuckDB's successful
  read-only lock plus stable pre/post bytes establishes the audited state used by
  this run.
- No copy, attach, export, checkpoint, vacuum, ALTER, INSERT, DELETE, UPDATE,
  CREATE, or other mutation was issued against the target database.
