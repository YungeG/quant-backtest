# Cross-project market-data acquisition programs and credentials

## Scope and secret-handling rule

This inventory identifies the programs and credential *names* used to acquire the
existing A-share and Binance data. It intentionally does not reproduce secret
values. No credential file was copied into Backtest.

## Critical security finding

The legacy backup repository contains a real-looking Tushare token in the tracked
file:

```text
/home/ygguo/agent-projs/_cleanup_backups/20260423_pre_cleanup/quant-a50/config/settings.json
```

The file is tracked, and the same real-looking value is present in the
`origin/main` version for remote `git@github.com:YungeG/quaaant.git`. The token
must be treated as compromised: revoke/rotate it, replace the tracked value with a
placeholder, and scrub Git history if the repository's exposure warrants it.

The current `cycle-rotation-platform` is safer: `.env` is ignored,
`.env.example` contains only `TUSHARE_TOKEN=YOUR_TUSHARE_TOKEN_HERE`, and
`config/settings.json` also contains a placeholder.

## A-share acquisition

### Credential matrix

| Source | Credential | Notes |
| --- | --- | --- |
| Tushare Pro | `TUSHARE_TOKEN` | Required. Endpoint access also depends on the account's Tushare permissions/points. |
| AkShare / Eastmoney / Sina adapters | none | Public endpoints; availability and schemas can drift. |
| Baostock | none | Uses the public login/session protocol at `public-api.baostock.com:10030`. |
| Local CSV → DuckDB import | none | Offline transformation only. |
| Existing DuckDB reads | none | Filesystem permission is sufficient. |

The preferred token injection is a process environment variable or ignored local
`.env`; do not store a real token in tracked JSON.

### Daily market and static data

Program:

```text
cycle-rotation-platform/operations/apps/fetch_data_tushare.py
```

APIs used:

- `stock_basic` for active instrument metadata;
- `daily` for per-symbol daily OHLCV/amount/change data.

Behavior:

- reads `TUSHARE_TOKEN` from environment/`.env`, with legacy fallback to
  `config/settings.json`;
- defaults to incremental fetch from the latest local CSV date;
- can initialize roughly five years or use an explicit start date;
- converts Tushare volume from lots to shares and amount to currency units;
- merges by date with `keep=last` and writes one CSV per symbol;
- writes `data/download_progress_tushare.json` with success/failure status.

Typical invocation:

```bash
cd /home/ygguo/agent-projs/cycle-rotation-platform
TUSHARE_TOKEN=... venv/bin/python operations/apps/fetch_data_tushare.py \
  --target-date YYYY-MM-DD
```

The existing market CSVs were later imported into
`/srv/bcache-8t/ygguo/duckdb/quant-a50/quant_a50.duckdb`.

### Fundamentals, listing metadata, and adjustment factors

Programs:

```text
cycle-rotation-platform/operations/apps/fetch_fundamentals_tushare.py
cycle-rotation-platform/operations/apps/backfill_daily_basic.py
quant-claude/operations/backfill_adj_factor.py
```

Tushare APIs include:

- `daily_basic`;
- `stock_basic`;
- `income`;
- `fina_indicator`;
- `adj_factor`.

All require `TUSHARE_TOKEN`. `daily_basic` has a recent-open-day fallback;
financial statements are fetched per symbol with pacing; `adj_factor` updates the
DuckDB table in place and is explicitly a manual, idempotent backfill.

### SW industry taxonomy, membership, and daily data

Program and wrapper:

```text
cycle-rotation-platform/operations/apps/fetch_industry_data_tushare.py
cycle-rotation-platform/operations/bin/fetch-industry-data
```

APIs:

- `index_classify(src="SW2021")`;
- `index_member_all(l3_code=..., is_new="Y"/"N")`;
- `sw_daily(start_date=..., end_date=...)`.

Behavior:

- requires `TUSHARE_TOKEN`;
- retrieves both current (`Y`) and historical (`N`) memberships;
- splits daily history into half-month requests;
- defaults to 1.3 seconds between calls;
- retries once with at least a 60-second wait on Tushare frequency-limit errors;
- writes taxonomy, membership, daily CSVs, fetch timestamps, and a manifest.

Example:

```bash
TUSHARE_TOKEN=... operations/bin/fetch-industry-data \
  --src SW2021 --start-date 20150101 --end-date YYYYMMDD --json
```

### Five-minute intraday data

Three implementations exist:

1. **Tushare** — `operations/apps/fetch_intraday_tushare.py`
   - requires `TUSHARE_TOKEN`;
   - calls `stk_mins` with a bounded symbol/date plan and row limit;
   - normalizes to `(ts_code, symbol, trading_day, timestamp, freq, OHLCV, amount)`;
   - replaces overlapping symbol/date rows before inserting into DuckDB.

2. **AkShare** — `operations/apps/fetch_intraday_akshare.py`
   - no key;
   - tries Eastmoney `stock_zh_a_hist_min_em` first;
   - falls back to Sina `stock_zh_a_minute`;
   - writes a JSON fetch report and optionally applies rows to DuckDB.

3. **Baostock** — `operations/apps/fetch_intraday_baostock.py`
   - no key;
   - calls `query_history_k_data_plus(..., frequency="5")` after public login;
   - supports task retries, logout/relogin, pacing, a consecutive-failure circuit
     breaker, JSON audit output, and overlap replacement in DuckDB.

Wrappers:

```text
operations/bin/fetch-intraday-tushare
operations/bin/fetch-intraday-akshare
operations/bin/fetch-intraday-baostock
```

Historical operations notes report that AkShare's Eastmoney path was flaky through
the proxy, Sina succeeded for required backfills, and Baostock sometimes failed at
login. The current DuckDB's conflicting intraday duplicates mean any reused slice
must be exported from an explicitly selected source/revision and revalidated.

### Offline import

Program:

```text
cycle-rotation-platform/operations/apps/import_to_duckdb.py
cycle-rotation-platform/operations/bin/import-to-duckdb
```

It imports local stock, market, fundamental, SW taxonomy/membership/daily, and
other CSV products into typed DuckDB tables. It needs no API key, but many imports
replace whole tables or overlapping ranges and stamp a new `UpdateAt`; therefore
the DuckDB is a mutable lake rather than immutable provider evidence.

## Binance acquisition

### Credential matrix

| Source/program | API key required? | Notes |
| --- | --- | --- |
| `data.binance.vision` public archives/checksums | no | Official public ZIP and adjacent `.CHECKSUM`. |
| `/fapi/v1/fundingRate`, klines, exchange info | no | Public market-data REST endpoints. |
| Public spot/futures WebSockets and depth snapshots | no | Recorder uses public streams and public REST snapshots. |
| `binance-ping` network probes | no | Uses `/fapi/v1/time` and public depth stream. |
| Live trading/Hummingbot order submission | yes | Separate concern; not required for any acquisition program listed here. |

Do not provide Binance trading credentials for historical/public-data work.

### Best existing raw archive downloader

Program:

```text
crypt-gemini/research/mm_l1_replay/fetch.py
crypt-gemini/research/mm_l1_replay/cli.py
```

Example:

```bash
cd /home/ygguo/agent-projs/crypt-gemini
python -m research.mm_l1_replay.cli fetch \
  --as-of 2024-03-31 --days 30 --output-dir /path/to/raw
```

It is stronger than the normalized carry downloader because it preserves raw
bytes and receipts:

- probes backward for a complete finite archive window;
- requires both ZIP and `.CHECKSUM` for every day;
- downloads ETHUSDT USD-M `bookTicker` and `aggTrades` daily archives;
- validates declared and streamed SHA-256 before atomic rename;
- retries 429 and 5xx responses up to five times with exponential waits;
- fetches funding history in ordered pages;
- stores each raw JSON response unchanged;
- hashes exact request parameters, response bytes, count, and last funding time;
- writes `raw_bundle_receipt.json`.

A large existing capture was found:

```text
/srv/bcache-8t/ygguo/crypt/mm_l1_engineering_20260720
size: about 200 GiB
raw receipt SHA-256:
  e731f0007a380601306ad0299aa542e015a6971b3e7094f75d45da9420553676
```

It contains official checksummed ETHUSDT `bookTicker` and `aggTrades` archives for
2024-03-01 through 2024-03-30, exact raw funding response bytes, request receipts,
normalized partitions, and a one-day verified manifest. Example 2024-03-01:

```text
bookTicker ZIP SHA-256:
  6b9a16fcf068f63a19098b9aba3da46823bca36b9123463a543c7e1926d84361
aggTrades ZIP SHA-256:
  67c9fe17b71283ac3fd4b2ab921cebcb6e97fafb3366a63e5daa45065f837689
```

The funding page contains 90 exact ETHUSDT rate+mark records:

```text
response SHA-256:
  23ba617d3c1d06512efeb0d26c1f994af889ce51b350136e20f207bac7020821
request-parameter SHA-256:
  795d7732095e40dc8ad5c148e01e587e5c9da98906ddce6849fe4e9226850ff2
```

This is immediately reusable for new Backtest ETHUSDT G12A/G12L fixtures without
network access. The archive files have provider checksums; the REST funding page
still lacks a provider revision/correction terminal set.

### Carry/audit downloader

Program:

```text
crypt-gemini/scripts/fetch_binance_carry_data.py
crypt-gemini/research/datafeed/binance_carry.py
```

Example:

```bash
python scripts/fetch_binance_carry_data.py \
  --symbols BTCUSDT ETHUSDT --start 2021-01-01 --end YYYY-MM-DD \
  --interval 1h --label LABEL --output-dir OUTPUT
```

It fetches spot/perpetual klines, funding history, and current exchange-info rules,
uses up to eight retries with rate-limit/server backoff, writes files atomically,
and creates a manifest with retrieval time, rows, URLs, and SHA-256. No API key is
required. It converts provider decimals to pandas numeric values, so it is useful
for broad parity and strategy research but not exact raw-decimal identity.

### Older kline/funding downloader

Program:

```text
crypt-gemini/research/datafeed/fetch_binance_crypto_data.py
```

It paginates USD-M klines and funding history, handles 418/429/5xx retries, and
writes per-symbol CSVs. No key is required. It retains less provenance than the
MM L1 downloader and drops funding mark price from its output.

### Live public microstructure recorder

Programs:

```text
crypt-gemini/.worktrees/binance-microstructure-recorder/
  scripts/record_binance_microstructure.py
  research/microstructure/recorder.py
  research/microstructure/storage.py
  research/microstructure/quality.py
```

Example:

```bash
python scripts/record_binance_microstructure.py \
  --output-dir /secure/capture/root --duration-seconds 60
```

No API key is required. It combines public Spot aggregate trades and Futures
trades with public depth streams and REST bootstrap snapshots. It reserves
paired event/session files securely, rejects sensitive/symlinked output paths,
uses capture IDs and inode identity, records reconnect/resync/error lifecycle,
and removes partial captures on failure. No sealed live capture was found locally;
only the recorder implementation is present.

### Network-quality probe

`binance-ping` requires no key. It probes DNS/TCP/TLS/REST latency against
`/fapi/v1/time`, clock quality, and `wss://fstream.binance.com` depth cadence/gaps.
It assesses connectivity and does not acquire historical market data.

## Backtest-owned acquisition implementation

The reusable subset is now imported into Backtest under `tools/acquisition/`:

- `binance_usdm.py` acquires checksummed USD-M `aggTrades`/`bookTicker` archives
  and exact funding-history REST bytes without credentials;
- `cn_a_share_tushare.py` acquires exact daily/listing JSON through fixed HTTPS
  requests using environment-only `TUSHARE_TOKEN`;
- both write atomic redacted receipts and candidate G12A snapshots;
- neither is imported by Runtime/Kernel or exposed from a package root.

Operational details: `docs/implementation/provider-acquisition-tools.md`.

## Recommended next use in Backtest

1. Use the existing 200-GiB MM L1 raw bundle before downloading more Binance
   data. Start with the small 9-KiB raw ETH funding page or the 2024-03-01
   checksummed `aggTrades` archive; do not copy the 10-GiB normalized bookTicker
   partition into Git.
2. For A-share, export a minimal canonical slice from the stable May-21 DuckDB
   backup; record the backup SHA-256 and exact query. Use Tushare only if the
   missing listing/action evidence must be reacquired.
3. Rotate the exposed Tushare token before running any Tushare program.
4. Keep all future credentials in environment/ignored `.env`; commit only
   placeholders and redacted acquisition receipts.
