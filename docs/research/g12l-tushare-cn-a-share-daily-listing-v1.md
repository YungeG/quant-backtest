# G12L Tushare China A-share Daily and Listing Evidence v1

## Decision status

`G12L-TUSHARE-CN-A-SHARE-DAILY-LISTING-V1` is `DRAFT / BLOCKED`.
The first Backtest-owned real Tushare acquisition is frozen for `000001.SZ`
(平安银行), trading date `2024-01-02`. It proves exact provider response capture,
G12A identity, and parity to the stable local DuckDB backup. It does not yet
authorize a normalized MarketEvent or Bundle.

## Acquisition authority

The source was acquired by the PASSED Backtest tool at immutable commit
`6f0bd99a93a349924996eb26708fbb0ac6fecf17`:

```bash
TUSHARE_TOKEN=... uv run --locked python \
  -m tools.acquisition.cn_a_share_tushare \
  --ts-code 000001.SZ --trade-date 20240102 \
  --output-dir <new-directory>
```

The tool sends fixed HTTPS `daily` and `stock_basic` requests, receives exact raw
JSON bytes, rejects credential echo, writes no token, publishes atomically, and
freezes a candidate G12A snapshot. The token itself is not evidence and is absent
from every fixture.

## Frozen source identity

| Member | SHA-256 |
| --- | --- |
| `daily.json` | `c2950a35c093b983e538f97830b7b3fcb0bba1a7dac98a17bd20f6db9296f846` |
| `stock-basic.json` | `d78fc472268deacb5af7c59c113325e2a00c5b4619c53fbbfe6fa23c96d471d2` |
| `acquisition-receipt.json` | `61106b7e974ff09dedf96c065070f4a097a7fe02121bfd7a81b5dacb5c4757da` |
| `evidence.expected.json` | `95775b9dc7ace840f52fbb6a2291ab2b34a92318a519fb8356a67d74ab776c43` |

```text
acquired_at_epoch_nanoseconds: 1786943026685846805
snapshot_id: sha256:6a360b17c1a5dd7686b2496f3b04006f902ef5705a1427dc2a7dbdaeadc2458a
content_tree_hash: sha256:44c4cd1e11dca26ddfe62fc1d2b5d4d8175da701b288876d33d1be65e06eddb5
provenance_hash: sha256:8745af52a950d0ba35eee381b32b6adad2d2ee144325de34ad3597389f2e73fb
```

Neither response carries a provider-declared checksum, so G12A
`declared_sha256` remains `null`; the hashes above are independently computed
content identities.

## Provider rows

Daily fields are:

```text
ts_code, trade_date, open, high, low, close, pre_close, change,
pct_chg, vol, amount
```

The exact row records `000001.SZ`, `20240102`, OHLC
`9.39/9.42/9.21/9.21`, volume `1158366.45` lots, and amount `1075742.252`
thousand CNY.

Listing fields preserve code, symbol, name, area, industry, board/market,
exchange, current list status, list date, and optional delist date. The exact
response identifies 平安银行 as an active Shenzhen main-board bank listed on
`19910403`.

## Stable DuckDB parity

Independent parity uses the stable local backup:

```text
/srv/bcache-8t/ygguo/duckdb/quant-a50/quant_a50.duckdb.backup_20260521_daily_basic_2015
sha256: cdc6ce41dee3fe9903d8c27ec5cc584455ad423989cd79e3eb0187c5bba8bd41
```

The daily OHLC and percentage change match exactly. Tushare volume lots map to
DuckDB shares by `×100`; Tushare amount thousands map to DuckDB currency units by
`×1000`. Listing code, name, area, industry, market, and list date also match.
The backup market row lacks `TSCode`, while its static row preserves
`000001.SZ`; this discrepancy is retained rather than silently repaired.

## Blocking semantics

No normalizer is authorized yet:

1. `trade_date` is an economic date, not a complete event timestamp. Builder must
   consume an approved A-share session-close authority rather than invent 15:00;
2. Tushare publishes JSON numbers rather than canonical decimal strings. Mapping
   must parse exact source text and freeze price/volume/amount scales and units;
3. current `stock_basic` is not a historical listing-status snapshot as of
   `2024-01-02` and has no correction/supersession terminal set;
4. Tushare provides no adjacent checksum, immutable publication revision, or
   correction closure for either response;
5. the only conservative availability is the later G12A acquisition time, so
   this cannot qualify a 2024 same-day replay;
6. corporate-action lifecycle evidence remains absent.

The slice therefore grants no G12B-D normalization/publication, G12I, G12K,
G12M, decision-grade, live, or deployment authority.
