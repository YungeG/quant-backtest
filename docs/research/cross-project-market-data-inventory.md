# Cross-project A-share and Binance market-data inventory

## Purpose

This inventory records reusable market-data evidence found outside Backtest under
`/home/ygguo/agent-projs`. It does not promote those files to Backtest authority.
Each candidate must be copied through a new Backtest-owned G12A snapshot with its
exact bytes, acquisition time, provenance, and limitations before use.

## A-share data

### Primary local lake

The strongest existing A-share source is the external DuckDB lake used by
`cycle-rotation-platform` and `quant-claude`:

```text
/srv/bcache-8t/ygguo/duckdb/quant-a50/quant_a50.duckdb
sha256: e06542cbf76d1043bf47e0660bf91b9cfbd90fab3c15616db50878271c8948b3
size: about 1.6 GiB
```

The current read-only inventory found:

| Table | Rows | Coverage / contents |
| --- | ---: | --- |
| `MarketData` | 10,727,596 | 5,323 symbols, daily OHLCV/amount, 2014-02-10 through 2026-08-14 |
| `DelistedMarketData` | 394,194 | 240 symbols, 2015-01-05 through 2026-04-13 |
| `StaticData` | 5,499 | active symbol, TS code, name, market, list date |
| `DelistedStaticData` | 242 | list and delist dates |
| `FundamentalData` | 11,069,691 | daily valuation/share/market-value fields, 2015-01-05 through 2026-08-14 |
| `IntradayData` | 3,513,072 | 2,065 symbols, five-minute bars, 2020-01-13 through 2026-04-20 |
| `IndustryDailyData` | 1,063,971 | SW industry daily data, 2015-01-07 through 2026-05-07 |
| `IndustryMemberData` | 7,652 | current/historical membership fields |
| `IndustryMemberHistoryData` | 1,812 | historical L1/L2/L3 membership |
| `IndustryTaxonomyData` | 511 | SW taxonomy |
| `MarginDetailData` | 6,105,951 | margin balances and intensity fields |

`MarketData.Source` is uniformly `tushare_compatible_csv`; the daily natural key
`(TradingDay, Symbol)` has no duplicates. `IntradayData` is not acceptance-ready:
there are 14,496 duplicate natural-key rows and 13,356 conflicting duplicate
groups.

The lake is mutable and not Git-bound. A stable local backup is also present:

```text
/srv/bcache-8t/ygguo/duckdb/quant-a50/quant_a50.duckdb.backup_20260521_daily_basic_2015
sha256: cdc6ce41dee3fe9903d8c27ec5cc584455ad423989cd79e3eb0187c5bba8bd41
size: about 761 MiB
```

That backup contains 10,439,983 daily market rows and is the safer source for a
finite reproducible A-share development slice. Example evidence exists for
`000001` on `2024-01-02`, plus its listing metadata. It still has no provider
checksum, exchange publication identity, correction terminal set, or historical
availability authority.

Source code and configuration:

- `cycle-rotation-platform/operations/apps/fetch_data_tushare.py`
- `cycle-rotation-platform/config/settings.json`
- `cycle-rotation-platform/config/platform/manifest.json`
- `quant-claude/factormine/data/`

### Git-tracked industry membership evidence

`cycle-rotation-platform` commit
`b3eb47115e8fbc01e5b1d523f02d1cb9feef85cf` tracks real SW2021 taxonomy and
membership evidence:

```text
config/evidence/industry_data/tushare/sw2021/index_classify.csv
sha256: 914f8efade775ba0db0ac22f5a1723fffa287ce66ad6cf2c8b54514f16fb58de

config/evidence/industry_data/tushare/sw2021/index_member_all.csv
sha256: e6921e4d70ce9f7d660128581535bfaf985201fe85addf5b5a63f8e98fa549c8
```

The membership file preserves L1/L2/L3 codes, symbol, in/out dates, current versus
historical status, and fetch time. It is useful input for a G12K membership slice.
The manifest references a 1,063,971-row `sw_daily.csv`, but that large CSV is not
present in the repository, so the manifest alone cannot authorize its bytes.

### Derived A-share artifacts

The following are useful for parity or diagnostics, not provider authority:

- `cycle-rotation-platform/data/staticdata_industry_panels.duckdb`, SHA-256
  `5a62fdcfc0eaba4ecb76ba54a207dd2f78dbb50d20362ad191e7f30066f73905`;
- `quant-claude/artifacts/factormine_cache/panel_640d80a84c935eff.parquet`,
  11,020,338 rows, SHA-256
  `7094d60ea5618cdedf7313c3c0a614c58a4060f49f23077c4b973ae203338c46`;
- `cycle-rotation-platform/artifacts/cache/n5_research_dataset.pkl`.

All three are untracked derived caches. The Parquet panel contains adjusted OHLC,
tradability masks, point-in-time size, and industry fields, but not raw provider
bytes or a provider revision chain. The pickle should not be imported as source
evidence.

No real corporate-action announcement/lifecycle dataset was found. Adjustment
factor tooling exists in `quant-claude/operations/backfill_adj_factor.py`, but the
current DuckDB inventory has no retained corporate-action table. G12K corporate
action closure therefore remains blocked.

## Binance data

### Raw checksummed MM L1 archive bundle

The strongest Binance source found is outside `agent-projs` but is owned by the
`crypt-gemini` acquisition program:

```text
/srv/bcache-8t/ygguo/crypt/mm_l1_engineering_20260720
```

It contains about 200 GiB of official ETHUSDT daily `bookTicker` and `aggTrades`
ZIPs with adjacent checksums, exact raw funding JSON pages and request receipts,
normalized partitions, and verified manifests for March 2024. The raw bundle
receipt SHA-256 is
`e731f0007a380601306ad0299aa542e015a6971b3e7094f75d45da9420553676`.
This is directly reusable for bounded Backtest G12A/G12L evidence. Details and
program commands are in `docs/research/cross-project-market-data-acquisition.md`.

### Hashed API-derived carry bundle

`crypt-gemini/artifacts/carry_audit_20260728/input/` contains the strongest broad
Binance bundle found. Its untracked manifest has SHA-256
`13875c8c17d97742db1d3a8e47c5ef503c97fd939987a04e8f9b4d98714bdbde`
and records:

- retrieval time `2026-07-28T09:19:03.125215+00:00`;
- exact Binance spot/perpetual kline, funding-history, and exchange-info URLs;
- BTCUSDT and ETHUSDT;
- 2021-01-01 through 2026-07-27;
- per-file row counts and SHA-256 hashes.

BTCUSDT examples:

| Kind | Rows | SHA-256 |
| --- | ---: | --- |
| funding | 6,102 | `67618d554a2bf66b6242077c2fa0cc8a3e439393c1c17706d4f2d7a5ee396f4e` |
| perpetual 1h | 48,816 | `9d36819c364b0d07ced06198ed92480e0ec63cde3a89b5616b6068b85a6f3e8f` |
| spot 1h | 48,802 | `7457b33f0a9be22387eeded95f30ee15a7efc4a31ee066732b771120a958b31c` |

The funding CSV includes mark prices from 2023-10-31 onward. Its three
2024-01-01 rows match the newly frozen Backtest funding-history response by value.
However, `research/datafeed/binance_carry.py` parses provider strings through
pandas numeric values before writing CSV. For example, provider
`42313.90000000` becomes `42313.9`. Raw JSON pages, response headers, page hashes,
and provider correction identities were not retained. The directory is also
untracked. It is therefore good independent parity evidence, but not canonical
G12A/G12L source authority.

### Prepared historical bundle

`crypt-gemini/artifacts/historical_bundle_8symbols/prepared/` contains eight
symbols with hourly, daily, and funding CSVs. Its market manifest SHA-256 is
`feae9f18944b799ff68ea51e7c3093d1c98c13bfe6c4ceb2391bf779f58535ca`.
Two bounded-source manifests additionally pin file size, row count, coverage, and
SHA-256; for example the weekly-ensemble manifest SHA-256 is
`bbdfbfde0a14e1bfce38a1c4ff4456849390ba0659864a3ddc3323abe0031de0`.

These are untracked normalized research inputs. Funding files omit mark price and
some conversions expose binary-float spellings, so they should be used only for
parity checks, not exact provider semantics.

### Microstructure recorder

The `crypt-gemini/.worktrees/binance-microstructure-recorder` worktree contains a
substantial append-only Binance recorder and audit implementation:

- `scripts/record_binance_microstructure.py`;
- `research/microstructure/capture.py`;
- `research/microstructure/recorder.py`;
- `research/microstructure/quality.py`;
- `docs/superpowers/specs/2026-07-11-one-second-microstructure-capture-design.md`.

It defines capture IDs, paired event/session files, source-order records, one-second
book snapshots, full trades, atomic storage, and quality audits. No actual local
`binance-microstructure-*-events.ndjson` capture or matching session file was found
under `agent-projs` or `/srv/bcache-8t/ygguo`. The code is reusable; the evidence is
not currently present.

`binance-ping` contains network-quality probes and a tiny synthetic depth-gap
fixture only, not reusable market history.

## Recommended Backtest use

1. **A-share first:** freeze a minimal daily-price/listing slice from the stable
   May-21 DuckDB backup, binding the backup SHA-256, exact read-only query, exported
   canonical bytes, and acquisition time. This can establish a real development
   G12L source and begin G12K listing/catalog work.
2. **Membership next:** separately ingest the Git-tracked SW2021 taxonomy and
   membership files for a real G12K membership fixture.
3. **Do not claim corporate-action closure:** no real action lifecycle source was
   found.
4. **Binance parity only:** use the carry-audit bundle to cross-check the Backtest
   2024 funding rate/mark values, not as canonical source bytes.
5. **Do not import derived caches:** the A-share Parquet/pickle and normalized
   Binance bundles are downstream research products, not provider authorities.
6. **If microstructure becomes necessary:** run and seal a new recorder capture;
   no historical local capture is available to import.
