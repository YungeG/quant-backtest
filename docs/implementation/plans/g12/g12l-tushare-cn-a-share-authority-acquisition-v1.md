---
id: G12L-TUSHARE-CN-A-SHARE-AUTHORITY-ACQUISITION-V1
readiness: READY_FOR_RED
gate_status: DRAFT
owner: Backtest tools/acquisition
produces:
  - exact current stock metadata response
  - exact historical name intervals
  - bounded adjacent adjustment-factor responses
  - exact target-date dividend response
  - candidate G12A snapshot and receipt
consumes:
  - Tushare Pro stock_basic, namechange, adj_factor, dividend
  - environment-only TUSHARE_TOKEN
depends_on:
  contract: [G12A, G12-ACQ-TOOLS-V1, G12-ACQ-TUSHARE-CALENDAR-V1]
  evidence: [official Tushare primary documentation]
fan_out: [G12L-TUSHARE-CN-A-SHARE-DAILY-LISTING-V1, G12K, G12M-CN-A-SHARE]
---

# G12L Tushare A-share Authority Acquisition v1

## Status

`READY_FOR_RED`. This freezes one additive acquisition program for exact
`000001.SZ / 2024-01-02` listing/name/corporate-action source evidence. It does
not modify the PASSED daily/listing or trade-calendar tools and grants no listing,
revision, corporate-action, decision-grade, or deployment qualification.

## Single tool seam

```text
TushareAuthorityRequest(
  ts_code,
  trade_date,
  previous_trade_date,
  next_trade_date,
)

acquire_listing_corporate_action_authority(
  request,
  *,
  token,
  output_dir,
  acquired_at_epoch_nanoseconds,
  post,
  sleep,
) -> dict[str, object]
```

The implementation belongs only in
`tools.acquisition.cn_a_share_tushare_authority`. It reuses the existing
provider-specific HTTPS/retry/response checks and common no-clobber publisher;
it adds no generic registry, adapter, credential store, cache, package export, or
Runtime/Trading Kernel import.

## Fixed provider requests

1. `stock_basic(ts_code=000001.SZ)` with exact list/delist fields;
2. `namechange(ts_code=000001.SZ)` with complete returned name intervals;
3. `adj_factor(ts_code=000001.SZ, start_date=20231229, end_date=20240103)`;
4. `dividend(ts_code=000001.SZ, ex_date=20240102)`.

Success requires one stock row whose documented list/delist interval covers the
trade date, exactly one name interval covering the trade date, exact unique
adjustment-factor rows for previous/target/next trading dates, and only target-date
dividend rows (zero is valid). Exact raw response bytes remain authoritative;
parsed binary floats are not numeric authority.

## Output and qualification

A new output directory contains exactly:

- `stock-basic.json`;
- `namechange.json`;
- `adj-factor.json`;
- `dividend-ex-date.json`;
- `acquisition-receipt.json`, written last.

The receipt binds exact request scopes, attempts, response hashes, row counts,
acquisition time, and one four-member candidate G12A snapshot. It fixes:

```text
provider_revision_id=null
revision_closure_complete=false
historical_listing_status_qualified=false
corporate_action_lifecycle_qualified=false
decision_grade_eligible=false
deployment_authorized=false
```

Provider or scope failure leaves the requested output absent. Existing output is
never replaced. Token material is accepted only as an injected/environment value
and must not appear in raw responses, receipts, exceptions, stdout, or committed
artifacts.

## RED command

```bash
uv run --locked pytest -q \
  tests/tools/acquisition/test_cn_a_share_tushare_authority.py \
  tests/architecture/test_g12l_tushare_authority_acquisition_boundary.py
```

## Explicit limits

- `stock_basic` is current metadata carrying documented list/delist dates, not a
  versioned historical status ledger;
- `namechange` proves only returned naming intervals;
- adjacent `adj_factor` and target-date `dividend` responses are finite captured
  evidence, not terminal corporate-action history;
- Tushare documentation currently supplies no immutable provider revision ID,
  checksum, correction history, or terminal-closure protocol;
- G12L, G12I/K/M, decision-grade, and deployment remain blocked until separate
  qualification evidence is accepted.
