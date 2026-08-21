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
fan_out: [G12L-BINANCE-USDM-FUNDING-HISTORY-SOURCE-BOUNDED-V2]
---

# G12L Binance USDⓈ-M Funding History v1

## Outcome

Freeze a finite real response proving that the official endpoint supplies exact
funding rate, funding-time mark, rate type, and funding time for G10E development.
This v1 retains the strict immutable-publication closure question. The additive
[source-bounded v2](g12l-binance-usdm-funding-history-source-bounded-v2.md)
normalizes and publishes the same byte-identical response under ADR 0008 without
changing v1.

Research authority: `docs/research/g12l-binance-usdm-funding-history-v1.md`.

## Status

`DRAFT / STRICT IMMUTABLE-PUBLICATION BLOCKED`. Exact request, repeated byte
identity, three response records, and G12A identity are frozen. The endpoint has no
provider checksum, immutable publication revision, or correction terminal set.
Those assurances still block this strict v1 lane, but are explicit limitations—not
ordinary historical-research blockers—for the accepted source-bounded v2 at
`024e5f209a94bb358946f5c468630108981f0329`, report
`sha256:29e639615c1e5f5fa05ffdff9bc77a630d56838c7b0e70230177922bdbffc37b`.

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

Until then no strict immutable-publication authority claim is warranted from v1.
The accepted source-bounded v2 separately provides exact normalization, G12C/D
publication identities, and one provider-specific G12M nominal seam; it does not
satisfy this strict provider-finality condition.
