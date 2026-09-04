---
id: G12L-BINANCE-USDM-MARK-PRICE-KLINES-V1
readiness: PASSED
gate_status: PASSED
owner: market-bundle-builder Binance USD-M source slice
produces:
  - exact Binance Public Data raw fixture evidence
  - SourceSnapshot via G12A
  - future provider-normalized MarketEvent evidence
consumes:
  - Binance Public Data daily USD-M markPriceKlines archive and checksum
  - G10D accepted mark-price source semantics
  - G12A-D contracts
depends_on:
  contract: [G10D, G12A, G12B, G12C, G12D]
  evidence: [Binance public-data commit 5c7f3197, frozen real archive bytes]
  write_conflict: [builder-root-exports, builder-provider-normalizer, acceptance-registry]
fan_out: [G12I, G12M-BINANCE-USDM]
---

# G12L Binance USDⓈ-M Daily Mark-Price-Kline v1

## Outcome

Qualify one exact Binance Public Data daily USD-M mark-price-kline source slice
through G12A-D without claiming generic Binance archive completeness, market
qualification, or deployment authorization.

Research authority:
`docs/research/g12l-binance-usdm-mark-price-klines-v1.md`.

## Current status

`PASSED` at immutable commit `47d59e40081555ab9b555c3e632070a517509436`.
Provider, dataset, authority revision, finite request, real ZIP/checksum, exact
G12A identity, conservative availability, bounded retry/failure behavior,
purpose-separated normalization, G12C/D evidence, full validation, and independent
review are frozen.

## Frozen v1 scope

- provider: Binance Public Data;
- authority revision: `binance-public-data@5c7f3197`;
- market/dataset: `futures/um/daily/markPriceKlines`;
- symbol/interval/date: `BTCUSDT`, `1m`, `2024-01-01` UTC;
- transport shape: exactly two unauthenticated HTTPS GETs for the named ZIP and
  adjacent `.CHECKSUM`; no listing, discovery, pagination, or current fallback;
- authoritative byte boundary: exact downloaded ZIP and checksum bytes;
- ZIP layout: one exact `BTCUSDT-1m-2024-01-01.csv` member;
- CSV closure: exact header and 1440 sequential one-minute closed rows;
- G12A identity: snapshot `sha256:df0869271a08320107381a60e9be9012d9645e076ef349c551d34aa332d2be80`.

## Minimum implementation seam

The Builder-owned
`crypto_quant_bundle_builder.binance_usdm_mark_price_archive` module implements
this exact provider grammar using only stdlib plus existing Domain, Market Data,
and G12A contracts. It stays off the already-frozen Builder root and adds no HTTP
library, SDK, generic transport Protocol, provider registry, adapter factory,
plug-in system, cache, credential store, filesystem scan, or Trading Kernel import.

The capture entry point receives the exact finite request plus an injected
provider-specific byte-fetch callable. It fetches only the two immutable URLs
with three bounded attempts, evaluates both terminal outcomes before applying the
common failure precedence, verifies both members, and calls
`freeze_source_snapshot()` only after complete success. Restart re-fetches the
whole two-member set; no partial state becomes authority.

The conservative v1 availability authority is the exact G12A archive member
`acquired_at_epoch_nanoseconds`: every normalized row uses that later instant as
`available_time`. Binance `close_time` remains the economic event/interval time
and never becomes publication evidence. This is deliberately fail-closed: the
2024 rows cannot qualify an intraday 2024 replay and G12M remains blocked until a
stronger immutable provider publication source is separately frozen.

Normalization may read the verified G12A ZIP member, exact-validate the one CSV,
and emit one atomic result with source↔event traces or one failure. The final
public type names and canonical result body are frozen by RED tests before the
production implementation is added.

## Mapping constraints

- preserve all provider timestamps and decimal strings exactly;
- bind `available_time` exactly to the G12A archive member acquisition timestamp;
  never infer it as `close_time + 1ms` or claim earlier provider publication;
- require closed rows and exact daily sequence closure;
- map close separately to VALUATION and MARGIN streams;
- map close plus low/high to LIQUIDATION evidence;
- never map this source to EXECUTION_REFERENCE, SETTLEMENT, or FUNDING;
- keep source ZIP/checksum/member hashes, row locator, snapshot ID, provenance
  hash, provider natural identity, and purpose-specific event identity;
- emit no event or snapshot after any checksum, ZIP, schema, row, closure, or
  mapping failure;
- keep `decision_grade_eligible=false` and `deployment_authorized=false`.

## Exact top-level failure precedence

1. `CONFIGURATION_INVALID`
2. `PROVIDER_UNAVAILABLE`
3. `AUTHENTICATION_REJECTED`
4. `RATE_LIMIT_EXHAUSTED`
5. `SOURCE_SCHEMA_MISMATCH`
6. `NORMALIZATION_FAILED`
7. `DATA_GAP_DETECTED`

Provisional provider mapping to freeze in tests:

- invalid symbol/interval/date/scope or unexpected URL → `CONFIGURATION_INVALID`;
- transport exception or exhausted retryable 5xx → `PROVIDER_UNAVAILABLE`;
- HTTP 401/403 → `AUTHENTICATION_REJECTED`;
- exhausted HTTP 429 → `RATE_LIMIT_EXHAUSTED`;
- checksum bytes, digest, ZIP member, encoding, header, or column shape invalid →
  `SOURCE_SCHEMA_MISMATCH`;
- invalid decimal/OHLC/timestamp/closed-row/Event mapping →
  `NORMALIZATION_FAILED`;
- HTTP 404, absent member, missing/duplicate/out-of-order minute, or non-exact
  UTC-day closure → `DATA_GAP_DETECTED`.

Multi-fault tests select the earliest code above; ties follow archive then
checksum request order and physical CSV row order.

## Frozen revision causal limit

The v1 revision is exactly the committed archive content hash plus adjacent
checksum at G12A acquisition instant `1786920753047737420`. It claims neither
latest status nor provider terminality beyond those bytes. Any later Binance
replacement is a new explicit slice/version and may not silently supersede this
snapshot. Every normalized event uses the archive content hash as revision ID
and records no invented supersedes link.

## Acceptance closure

- focused G12L: 11 passed;
- full repository: 1726 passed;
- import boundaries: 107 files passed;
- root lock, diff, LSP, lens, and secret scan: clean;
- independent review: `NONE`;
- G12I/G12M remain separate and unqualified.

## Current executable evidence

```bash
uv run --locked pytest -q \
  tests/bundle_builder/providers/binance_usdm \
  tests/architecture/test_g12l_binance_mark_price_boundary.py
```

This check is deliberately narrower than Gate acceptance. It freezes the real
raw fixture and G12A handoff so later code cannot invent or silently replace the
source contract.
