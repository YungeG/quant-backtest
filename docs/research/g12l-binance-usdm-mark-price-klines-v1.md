# G12L Binance USDⓈ-M Daily Mark-Price-Kline Evidence v1

## Decision status

The first concrete G12L source is selected: Binance Public Data, USD-M futures,
`daily/markPriceKlines`, `BTCUSDT`, `1m`, UTC date `2024-01-01`.

This note freezes source evidence and the exact G12A handoff only. The concrete
slice remains `DRAFT / IN PROGRESS` until provider normalization, retry/failure
behavior, archive-revision closure, G12B-D publication, and acceptance are
implemented. It grants no G12I, G12M, decision-grade, live, or deployment claim.

## First-party authority

Binance's public-data repository states that public market data is published as
daily or monthly files and that every ZIP has an adjacent `.CHECKSUM` file. Its
futures downloader documentation identifies `um` as USD-M Futures and provides a
dedicated `markPriceKlines` downloader with explicit symbol, interval, year,
month, date, and checksum arguments.

Frozen authority revision: Binance `binance-public-data` commit `5c7f3197`.

| Authority | Immutable URL | Retrieved byte SHA-256 |
| --- | --- | --- |
| Public-data README | <https://github.com/binance/binance-public-data/blob/5c7f3197/README.md> | `085ab91377aa9325d44f4c7ad27cce4ab381e158403e1d7df2bad39d1a66f7c6` |
| Downloader README | <https://github.com/binance/binance-public-data/blob/5c7f3197/python/README.md> | `5d5e3a0bd69469bad8addb0e2db3015b6bf8ada10ce71a8ae81d5d1e5b792b8c` |
| Mark-price downloader | <https://github.com/binance/binance-public-data/blob/5c7f3197/python/download-futures-markPriceKlines.py> | `e701b6dc4104c688285b1a17ef42833f65061a34d1555e7c94dedc1c5ed156a3` |
| Mark-price-kline field semantics | <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Mark-Price-Kline-Candlestick-Data> | cited by the accepted G10D source-semantics note |

The public archive requires no authentication. Acquisition is two finite HTTPS
GETs; no latest/current/now endpoint, directory listing, pagination, symbol
discovery, wall-clock expansion, SDK, credential, or runtime network client is
part of this slice.

## Exact finite source scope

```text
provider: Binance Public Data
market: USD-M Futures
dataset: daily markPriceKlines
symbol: BTCUSDT
interval: 1m
UTC date: 2024-01-01
archive URL: https://data.binance.vision/data/futures/um/daily/markPriceKlines/BTCUSDT/1m/BTCUSDT-1m-2024-01-01.zip
checksum URL: https://data.binance.vision/data/futures/um/daily/markPriceKlines/BTCUSDT/1m/BTCUSDT-1m-2024-01-01.zip.CHECKSUM
```

The exact retrieved bytes are committed under
`tests/fixtures/market_data/providers/binance_usdm/mark-price-klines-v1/`.

| Member | Byte count | SHA-256 |
| --- | ---: | --- |
| `BTCUSDT-1m-2024-01-01.zip` | 33182 | `660efeefdc875f052051b94c2976babd013f64c6633bf58ba030764771747b90` |
| `BTCUSDT-1m-2024-01-01.zip.CHECKSUM` | 92 | `ea5548dadd83fad69bbc9db3a24560b7d3f988e54299d2c6aa87e85351e05215` |
| ZIP member `BTCUSDT-1m-2024-01-01.csv` | 140721 | `71357549ea1f81632e92f1b2ee2677c173a51e8563b0d5dd26ee4f321c7eb378` |

The checksum file exact-matches the committed ZIP. The ZIP contains exactly one
CSV member. The CSV has the provider header
`open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore`
and exactly 1440 records. Open times exact-cover the UTC day in 60,000 ms steps;
each close time equals open time plus 59,999 ms. This proves internal fixture
closure only, not that Binance will never replace the archive or that the day
was free from exchange/provider outages.

## Exact G12A handoff

The raw ZIP and checksum bytes are separate `0644` G12A members. They share the
caller-recorded acquisition instant `1786920753047737420` epoch nanoseconds and
use these provenance keys:

```text
vendor_key: binance.public_data
source_key: binance.public_data.futures.um.daily.mark_price_klines.btcusdt.1m.2024-01-01
license_ref: binance.public_data.terms
retention_policy_ref: backtest.fixture.retention
```

Frozen outputs:

```text
snapshot_id: sha256:df0869271a08320107381a60e9be9012d9645e076ef349c551d34aa332d2be80
content_tree_hash: sha256:9b12fcf35779d78b2d0293692deb595d54b4506bbb9da6dde44e525a8c968b32
provenance_hash: sha256:4dba4a7b2140ac82bc7c736f856b1fa8ea0d2ff58e8e5f7c659f4cb870aed2ca
```

The executable fixture test verifies checksum, ZIP layout, CSV grammar, exact
one-day sequence closure, OHLC ordering, repeated G12A identity, and false
qualification flags without network access.

## Mapping boundary retained from G10D

The accepted G10D primary-source decision remains authoritative:

- only closed mark-price-kline rows are eligible;
- close may feed separate VALUATION and MARGIN evidence;
- close plus low/high may feed LIQUIDATION point/bar evidence;
- the same raw row does not merge PricePurpose identities;
- mark-price data cannot create EXECUTION_REFERENCE, SETTLEMENT, or FUNDING
  evidence;
- provider open/high/low/close decimal strings and millisecond times remain exact;
- archive capture time is not substituted for economic event/close time.

G12L still needs a Builder-owned provider normalizer and source↔event trace, but
that normalizer is currently blocked: the CSV proves provider close times, not
when each final row became knowable. `available_time = close_time + 1ms` would be
invented, while archive capture time would make every 2024 event unavailable
until the later capture. A separate immutable per-row publication/availability
authority or authoritative bounded derivation rule must be frozen first. The
future normalizer must not import Trading Kernel provider types or label provider
rows as the existing synthetic JSONL grammar.

## Remaining closure work

1. Freeze immutable publication/availability evidence for every row or an exact
   authoritative bounded derivation rule; provider close time alone is not enough.
2. Freeze the provider-specific, purpose-separated normalization result and exact
   mapping to generic `MarketEvent` values without adding a generic adapter framework.
3. Implement strict checksum/ZIP/CSV validation and atomic mapping failures,
   including malformed/encrypted ZIP members and mixed-fault precedence.
4. Freeze bounded transport retry/restart behavior with injected offline fakes;
   no partial G12A handoff may escape.
5. Map HTTP/provider and content failures to the common G12L precedence.
6. Prove archive revision/correction terminality or record a finite causal limit;
   the public README explicitly permits later archive updates.
7. Produce G12C manifest and G12D publication evidence from the normalized set.
8. Keep G12I/G12M and all decision/live/deployment flags false until their own
   provider-backed closure evidence passes.
