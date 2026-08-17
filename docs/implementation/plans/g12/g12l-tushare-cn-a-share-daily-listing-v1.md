---
id: G12L-TUSHARE-CN-A-SHARE-DAILY-LISTING-V1
readiness: BLOCKED
gate_status: DRAFT
owner: market-bundle-builder China A-share source slice
produces:
  - exact Tushare daily/listing response evidence
  - Backtest acquisition receipt
  - SourceSnapshot via G12A
consumes:
  - Tushare Pro daily and stock_basic responses
  - stable quant-a50 DuckDB backup parity row
depends_on:
  contract: [G12A, G12-ACQ-TOOLS-V1]
  evidence: [real Tushare response bytes, stable DuckDB backup]
fan_out: [G12B-A-SHARE-DAILY, G12K, G12M-CN-A-SHARE]
---

# G12L Tushare China A-share Daily and Listing v1

## Outcome

Freeze one exact real A-share provider capture and independent local-lake parity
before defining normalized daily-price or listing-lifecycle events.

Research authority:
`docs/research/g12l-tushare-cn-a-share-daily-listing-v1.md`.

## Status

`DRAFT / BLOCKED`. Exact acquisition request, raw response bytes, receipt,
G12A identity, token-redaction proof, and DuckDB parity are frozen. No normalizer
or G12C/D publication is authorized.

## Frozen scope

- provider: Tushare Pro;
- instrument: `000001.SZ` / 平安银行;
- trading date: `2024-01-02`;
- APIs: `daily` and `stock_basic`;
- one exact row from each response;
- exact acquisition time and candidate G12A snapshot;
- parity to immutable local DuckDB backup SHA-256;
- no token bytes in fixtures or receipts;
- all qualification flags false.

## Remaining blockers

1. Freeze a Builder-owned A-share session/date-to-event-time declaration exact-
   bound to the accepted G08H calendar/session authority.
2. Freeze exact source-text decimal, unit, and scale mapping for OHLC, volume lots,
   amount thousands, and percentage change.
3. Decide whether current `stock_basic` may only provide instrument metadata or
   can support any historical listing claim; default is metadata only.
4. Obtain provider revision/correction terminal evidence or retain the finite
   causal limit explicitly.
5. Freeze normalized G12B schemas and failure precedence before implementation.
6. Keep corporate actions, G12I, G12K final reports, G12M, decision-grade, and
   deployment separate.

## Current executable evidence

```bash
uv run --locked pytest -q \
  tests/bundle_builder/providers/tushare/test_cn_a_share_daily_listing_evidence.py
```
