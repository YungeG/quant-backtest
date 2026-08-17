# Provider acquisition tools v1

## Status

`PASSED` at immutable commit `6f0bd99a93a349924996eb26708fbb0ac6fecf17`.

Backtest now owns reproducible source acquisition programs in
`tools/acquisition/`. They are side-effect adapters outside runtime packages;
the existing G12A and provider normalizers remain pure and unchanged.

## Interfaces

### Binance USD-M

```bash
uv run --locked python -m tools.acquisition.binance_usdm archive \
  --symbol ETHUSDT --kind aggTrades --date 2024-03-01 \
  --output-dir /absolute/new/output

uv run --locked python -m tools.acquisition.binance_usdm funding \
  --symbol ETHUSDT --start-ms 1709251200000 --end-ms 1709337599999 \
  --limit 1000 --output-dir /absolute/new/output
```

No API key is required. The archive command downloads the exact ZIP and adjacent
`.CHECKSUM`, retries bounded 429/5xx failures, verifies filename binding and
SHA-256, publishes atomically, and freezes a candidate G12A snapshot. The funding
command preserves exact raw REST bytes, validates finite ordered scope, writes a
redacted request receipt, and freezes a one-member candidate snapshot.

Supported archive kinds are deliberately limited to the imported acquisition
method: `aggTrades` and `bookTicker`.

### Tushare A-share daily/listing

```bash
TUSHARE_TOKEN=... uv run --locked python \
  -m tools.acquisition.cn_a_share_tushare \
  --ts-code 000001.SZ --trade-date 20240102 \
  --output-dir /absolute/new/output
```

The token is accepted only from the process environment. The tool never reads
tracked configuration, prints the token, or persists a request body containing
it. It sends fixed HTTPS `daily` and `stock_basic` requests, preserves exact raw
JSON responses, validates one-row scope, publishes atomically, and freezes a
candidate two-member G12A snapshot.

The legacy token discovered in the old `quant-a50` Git history must be rotated
before this command is used.

## Output contract

Every successful command creates a previously nonexistent directory containing:

- exact provider source bytes;
- `acquisition-receipt.json` with request scope, attempts, hashes, G12A snapshot,
  and false qualification flags.

The output directory is claimed with no-clobber `mkdir`; files are fsynced and the
receipt is written last as the publication marker. Any provider, checksum, schema,
scope, decoded token-echo, or snapshot failure leaves the requested output absent.
A concurrently created output is preserved and never replaced.

`declared_sha256` is populated only for archive bytes whose hash is declared by
Binance's adjacent checksum. Checksum files and REST/Tushare responses retain only
their independently computed G12A content hash.

## Acceptance closure

- focused acquisition and architecture: 20 passed;
- full repository: 1765 passed;
- import boundaries: 109 files passed;
- lock, diff, LSP, lens, and secret scan: clean;
- independent review: `NONE`;
- real Binance smoke reproduced the accepted BTCUSDT 2020-01-01 aggregate-trades
  ZIP/checksum hashes and the BTCUSDT 2024-01-01 funding-history response hash;
- an invalid-token Tushare HTTPS smoke failed atomically without persisting or
  printing the credential.

## Boundaries

- no Backtest Runtime or Trading Kernel import;
- no Builder root export or public-package API change;
- no generic provider registry, factory, credential store, cache, or transport
  Protocol;
- no network tests;
- only standard-library HTTPS adapters in executable commands;
- tests use injected provider-specific fakes and committed byte literals;
- acquisition receipts are candidates, not PASSED G12L evidence;
- `decision_grade_eligible=false` and `deployment_authorized=false` remain fixed.
