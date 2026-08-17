---
id: G12L-BINANCE-USDM-FUNDING-RATE-V1
readiness: PASSED
gate_status: PASSED
owner: market-bundle-builder Binance USD-M source slice
produces:
  - exact Binance funding-rate raw evidence
  - SourceSnapshot via G12A
  - future funding-rate publication MarketEvent stream
consumes:
  - Binance Public Data monthly USD-M fundingRate archive and checksum
  - G10E funding source semantics
  - G12A-D contracts
depends_on:
  contract: [G10E, G12A, G12B, G12C, G12D]
  evidence: [binance-public-data@5c7f3197, frozen real archive bytes]
fan_out: [G12I, G12M-BINANCE-USDM]
---

# G12L Binance USDⓈ-M Monthly Funding Rate v1

## Outcome

Qualify one exact Binance Public Data monthly funding-rate slice through G12A-D
without manufacturing the absent funding-time mark or claiming market readiness.

Research authority: `docs/research/g12l-binance-usdm-funding-rate-v1.md`.

## Current status

`PASSED` at immutable commit `ebd91f746c4a065ca06dba89d847e7d41ab06331`.
Exact capture, global precedence, atomic restart, three-field normalization, jitter,
scientific rates, request/source binding, traces, and G12C/D are frozen.

## Minimum implementation seam

Add one internal Builder provider module, off the frozen root. Reuse the accepted
exact request/capture/snapshot authority pattern. Emit one
`binance_usdm.funding-publications` stream containing raw and exact normalized
funding rates. Do not add a common adapter, registry, transport Protocol, HTTP
dependency, cache, Trading Kernel import, or funding mark.

## Failure precedence

1. `CONFIGURATION_INVALID`
2. `PROVIDER_UNAVAILABLE`
3. `AUTHENTICATION_REJECTED`
4. `RATE_LIMIT_EXHAUSTED`
5. `SOURCE_SCHEMA_MISMATCH`
6. `NORMALIZATION_FAILED`
7. `DATA_GAP_DETECTED`

## Acceptance closure

- focused provider and boundaries: 29 passed;
- full repository: 1744 passed;
- import boundaries: 109 files passed;
- lock, diff, LSP, lens, network isolation, and secret scan: clean;
- independent review: `NONE`;
- the missing funding-time mark, G10E completion, G12I, and G12M remain unqualified.
