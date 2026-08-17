---
id: G12L-BINANCE-USDM-AGGTRADES-V1
readiness: READY
gate_status: DRAFT
owner: market-bundle-builder Binance USD-M source slice
produces:
  - exact Binance aggregate-trades raw evidence
  - SourceSnapshot via G12A
  - future EXECUTION_REFERENCE MarketEvent stream
consumes:
  - Binance Public Data daily USD-M aggTrades archive and checksum
  - G10D aggregate-trade source semantics
  - G12A-D contracts
depends_on:
  contract: [G10D, G12A, G12B, G12C, G12D]
  evidence: [binance-public-data@5c7f3197, frozen real archive bytes]
fan_out: [G12I, G12M-BINANCE-USDM]
---

# G12L Binance USDⓈ-M Daily Aggregate Trades v1

## Outcome

Qualify one exact Binance Public Data daily aggregate-trade slice through G12A-D
and produce the real EXECUTION_REFERENCE source stream without claiming generic
archive completeness or market qualification.

Research authority: `docs/research/g12l-binance-usdm-aggtrades-v1.md`.

## Current status

`DRAFT / READY FOR ACCEPTANCE`. Exact capture, bounded retries, failure mapping,
headerless seven-field normalization, contiguous aggregate-trade IDs, exact G12A
identity, conservative availability, source traces, and G12C/D evidence are frozen.

## Frozen scope

- USD-M `daily/aggTrades`, `BTCUSDT`, `2020-01-01` UTC;
- exactly two unauthenticated fixed HTTPS members;
- ZIP contains one exact `BTCUSDT-aggTrades-2020-01-01.csv`;
- 71,359 rows with contiguous aggregate IDs `18374167..18445525`;
- exact provider price scale ≤2, quantity scale ≤3, millisecond trade time;
- `available_time` equals the G12A archive acquisition instant;
- normalized purpose is only `EXECUTION_REFERENCE`;
- no header/current endpoint/pagination/latest fallback.

## Minimum implementation seam

Add one provider module off the frozen Builder root. Reuse the mark-price slice's
proven pattern: exact request, two-member bounded capture, full snapshot/provenance
revalidation, replacement rejection, strict ZIP/CSV parsing, one source trace per
row, G12C stream manifest, and G12D publication. Do not create a common adapter,
registry, transport Protocol, HTTP dependency, cache, or Trading Kernel import.

## Failure precedence

1. `CONFIGURATION_INVALID`
2. `PROVIDER_UNAVAILABLE`
3. `AUTHENTICATION_REJECTED`
4. `RATE_LIMIT_EXHAUSTED`
5. `SOURCE_SCHEMA_MISMATCH`
6. `NORMALIZATION_FAILED`
7. `DATA_GAP_DETECTED`

## Acceptance work remaining

1. Run focused and full repository tests, import boundaries, network isolation,
   secret scan, lock check, LSP, and diff checks.
2. Obtain independent review with no material findings.
3. Freeze the accepted implementation commit and change this slice to `PASSED`.
4. Keep G12I/G12M separate and unqualified.

## Current executable evidence

```bash
uv run --locked pytest -q \
  tests/bundle_builder/providers/binance_usdm/test_aggtrades_archive_evidence.py
```
