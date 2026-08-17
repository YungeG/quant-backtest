---
id: G12L-BINANCE-USDM-FUNDING-HISTORY-V1
readiness: BLOCKED
gate_status: DRAFT
owner: market-bundle-builder Binance USD-M source slice
produces:
  - exact finite Funding Rate History response evidence
  - SourceSnapshot via G12A
consumes:
  - Binance USD-M Funding Rate History REST response
  - G10E funding source semantics
  - G12A contract
depends_on:
  contract: [G10E, G12A]
  evidence: [official Binance Funding Rate History documentation]
fan_out: [G12L-BINANCE-USDM-FUNDING-HISTORY-V2]
---

# G12L Binance USDⓈ-M Funding History v1

## Outcome

Freeze a finite real response proving that the official endpoint supplies exact
funding rate, funding-time mark, rate type, and funding time for G10E development.
Do not normalize or publish it as accepted G12B-D authority without immutable
provider revision/correction closure.

Research authority: `docs/research/g12l-binance-usdm-funding-history-v1.md`.

## Status

`DRAFT / BLOCKED`. Exact request, repeated byte identity, three response records,
and G12A identity are frozen. The endpoint has no provider checksum, immutable
publication revision, or correction terminal set. Adding a normalizer now would
only wrap evidence that cannot pass the common G12L READY checklist.

## Frozen finite scope

- `BTCUSDT`, 2024-01-01 UTC;
- exact `startTime=1704067200000`, `endTime=1704153599999`, `limit=100`;
- no key/signature, pagination, latest/current fallback, or symbol discovery;
- exactly three records at 00:00, 08:00, and 16:00 UTC;
- exact fields: symbol, fundingTime, fundingRate, markPrice, rateType;
- G12A availability equals the later capture time;
- all qualification flags remain false.

## Unblock condition

Provide one of:

1. an immutable first-party archive/checksum containing both rate and funding
   mark for the finite scope; or
2. first-party revision/correction evidence that closes the exact REST result.

Until then no provider normalizer, G12C manifest, G12D publication, G12I, or G12M
claim is warranted.
