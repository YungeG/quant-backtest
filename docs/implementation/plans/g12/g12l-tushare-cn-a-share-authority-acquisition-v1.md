---
id: G12L-TUSHARE-CN-A-SHARE-AUTHORITY-ACQUISITION-V1
readiness: EVIDENCE_FROZEN
gate_status: ACCEPTANCE_PENDING
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

`EVIDENCE_FROZEN / ACCEPTANCE_PENDING`. The additive acquisition program produced
one real no-clobber capture for exact `000001.SZ / 2024-01-02`
listing/name/corporate-action source evidence. Independent review and full-repository
acceptance remain pending. The PASSED daily/listing and trade-calendar tools remain
unchanged, and no listing, revision, corporate-action, decision-grade, or deployment
qualification is granted.

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

Success requires exact unique-key provider envelopes with `has_more=false` and
integer `count=0`, one stock row whose documented list/delist interval covers the
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

## Focused command

```bash
uv run --locked pytest -q \
  tests/tools/acquisition/test_cn_a_share_tushare_authority.py \
  tests/architecture/test_g12l_tushare_authority_acquisition_boundary.py
```

Focused implementation and inherited acquisition checks: 15 passed.

## Frozen real capture

- implementation commit: `538cf2873e647c61405052e4b7631fdc39e25122`;
- acquisition time: `1787021168783113919` ns;
- snapshot: `sha256:bd8ae548949696f1c98f8a20b5c8653f64121fc2eee61c1ff2ac21a97d248c0d`;
- provenance: `sha256:f0e938a25f952cc5ba6ce5300975927a7956099ce4fd899cb99cf21538d9e8ca`;
- `stock_basic`: `sha256:93cba2aa17cc927cf454d4de962d2f18a099a9576cf044add502626df3075af4`;
- `namechange`: `sha256:9a4982b500c54001160f958c618a99092d7859d56da21dbaea58963e89db82d4`;
- `adj_factor`: `sha256:4830a62041922615a68d9b31b5a9ee608fdeb3835e52ba308fede59622422df8`;
- `dividend(ex_date=20240102)`: `sha256:cc1a888c81aef5e93097951eb25ea14e14744e1a5cf3b3da2eea5cb561609a7d`;
- receipt file: `sha256:5f2e6f2c3870cdc26c93a2e15e5842888b890cb8d20ad5d5b16ed19882771276`;
- rows: stock 1, namechange 4, adjacent factors 3, target-date dividend 0;
- all provider-revision/listing/corporate-action/decision/deployment qualifications remain false.

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
