---
id: G12L-BINANCE-USDM-MARK-PRICE-KLINES-V1
readiness: IN_PROGRESS
gate_status: DRAFT
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

`DRAFT / IN PROGRESS`. Provider, dataset, immutable authority revision, finite
request scope, real ZIP/checksum fixtures, internal one-day closure, and exact
G12A snapshot identity are frozen. Provider normalization, bounded transport
behavior, revision terminality, G12C/D evidence, and final acceptance remain.

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

Add one Builder-owned module for this exact provider grammar. It may use stdlib
`csv`, `hashlib`, `io`, and `zipfile`, plus existing Domain/Market Data/G12A
public contracts. It must not add an HTTP library, SDK, generic transport
Protocol, provider registry, adapter factory, plug-in system, cache, credential
store, filesystem scan, or Trading Kernel import.

The executable entry point receives the exact finite request plus an injected
provider-specific byte fetch callable. It fetches only the two derived immutable
URLs with a frozen bounded retry count, verifies both members, and calls
`freeze_source_snapshot()` only after complete success. A restart re-fetches the
whole two-member set; no partial resume state becomes authority.

Normalization reads the verified G12A ZIP member, exact-validates the one CSV,
and emits one atomic result with source↔event traces or one failure. The final
public type names and canonical result body are frozen by RED tests before the
production implementation is added.

## Mapping constraints

- preserve all provider timestamps and decimal strings exactly;
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

## Acceptance work remaining

1. Add RED contract tests for request/result/failure canonical identities.
2. Add offline fake-fetch tests for uninterrupted, retry, restart, duplicate
   response, exhausted retry, and every HTTP/content failure mapping.
3. Implement the minimal provider module and exact source↔event trace.
4. Produce and freeze normalized, G12C manifest, and G12D publication fixtures.
5. Record archive revision/correction closure or an explicit finite causal limit.
6. Run focused, full repository, import-boundary, network-isolation, secret scan,
   lock, LSP, and independent review checks.
7. Only then change the concrete slice to `PASSED`; G12I/G12M remain separate.

## Current executable evidence

```bash
uv run --locked pytest -q \
  tests/bundle_builder/providers/binance_usdm/test_mark_price_archive_evidence.py
```

This check is deliberately narrower than Gate acceptance. It freezes the real
raw fixture and G12A handoff so later code cannot invent or silently replace the
source contract.
