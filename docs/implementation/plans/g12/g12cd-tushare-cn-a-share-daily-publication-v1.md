---
id: G12CD-TUSHARE-CN-A-SHARE-DAILY-PUBLICATION-V1
readiness: IMPLEMENTED
gate_status: ACCEPTANCE_PENDING
owner: market-bundle-builder internal Tushare daily publication projection
produces:
  - one development-only MarketEvent from one accepted Tushare daily normalization result
consumes:
  - G12B-TUSHARE-CN-A-SHARE-DAILY-V1 normalization result
  - unchanged G12C validation and G12D local publication seams
depends_on:
  contract: [G12B-TUSHARE-CN-A-SHARE-DAILY-V1, G12C, G12D]
  evidence: [g12l-tushare-cn-a-share-daily-listing-v1]
fan_out: [G12I, G12K, G12M-CN-A-SHARE]
---

# G12C/D Tushare China A-share Daily Publication v1

## Status

`IMPLEMENTED / ACCEPTANCE_PENDING`. One development-only projection now composes
through the already accepted G12C/D seams with exact event, manifest, publication,
and replay fixtures. Independent review and full-repository acceptance remain
pending; this status does not authorize G12L/provider qualification.

## Single internal seam

```text
project_tushare_cn_a_share_daily_market_event_v1(
  result: TushareCnAShareDailyNormalizationResult,
) -> MarketEvent
```

The function belongs only in
`crypto_quant_bundle_builder.tushare_cn_a_share_daily_bundle`, with no Builder
root export. It returns one provider-specific
`tushare_cn_a_share.daily-publications@1` event in
`tushare_cn_a_share.daily.publication.xshe.000001.v1` with type
`tushare_cn_a_share_daily_publication.v1`. It deliberately does not claim the
generic `price.bar@1`/`price_bars@1` capability because this finite source
publication has no single executable price purpose:

- event time is the raw Bar bucket's `interval_start`; finality remains nested in
  that bucket as `interval_end_exclusive`;
- availability, instrument, revision, source key, and source hash bind exactly to
  the accepted raw Bar/trace; source sequence is `0` at `market_data` phase;
- event ID is `tushare-cn-a-share-daily-v1:<normalization_hash>`.

Its canonical payload has exactly `normalization_hash`, `raw_bar`, `source_trace`,
`execution_reference`, `valuation`, and `qualification`. The nested raw Bar is
purpose-free. The two nested projections remain explicit and respectively carry
`execution_reference` and `valuation`; they are not collapsed into a shared
price-purpose field. `qualification` is exactly:

```text
revision_closure_complete=false
historical_listing_status_qualified=false
corporate_actions_qualified=false
decision_grade_eligible=false
deployment_authorized=false
```

## Required composition

The provider contract test must pass the returned one-event tuple unchanged to
`validate_market_bundle_v1`, serialize that unchanged stream with
`canonical_bytes`, and publish it with `LocalMarketBundleRepository`. G12C and
G12D code, APIs, and root exports remain unchanged. No adapter, Protocol, factory,
registry, repository wrapper, Reader, root export, or network path is introduced.

## Implementation evidence and blockers

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --locked pytest -q \
  tests/bundle_builder/providers/tushare/test_cn_a_share_daily_bundle.py \
  tests/architecture/test_g12cd_tushare_daily_bundle_boundary.py
```

The focused projection, architecture, G12C validation, G12D first publication,
and idempotent replay checks pass. This does not make G12L/listing, provider revision
closure, corporate actions, G12I, G12K, G12M, decision grade, or deployment ready.
