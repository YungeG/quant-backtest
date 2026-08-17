---
id: G12L-BINANCE-USDM-AGGTRADES-V1
readiness: IN_PROGRESS
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

`DRAFT / IN PROGRESS`. Provider, authority revision, finite archive/checksum,
headerless seven-field grammar, contiguous aggregate-trade IDs, exact G12A
identity, and conservative acquisition-time availability are frozen.

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

1. Freeze RED request/capture/normalization/failure tests.
2. Implement exact capture and one execution-reference stream.
3. Prove replacement/provenance/missing-member/malformed archive rejection.
4. Freeze G12C/D hashes and exact revision causal limit.
5. Run full validation and independent review, then accept the immutable commit.

## Current executable evidence

```bash
uv run --locked pytest -q \
  tests/bundle_builder/providers/binance_usdm/test_aggtrades_archive_evidence.py
```
