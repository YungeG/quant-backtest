---
id: G12CD-TUSHARE-CN-A-SHARE-DAILY-PUBLICATION-V1
readiness: PASSED
gate_status: PASSED
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

`PASSED` at immutable implementation revision
`7400cad6531b2687ffb150959cbf534c6797359e`. One development-only projection
composes through the already accepted G12C/D seams with exact event, manifest,
publication, replay, and authority-hardening evidence. This status does not
authorize G12L/provider qualification.

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

Acceptance closure:

- RED contract: `2d0470440eea2e4f84ef6ffab5efca0fb8263516`;
- implementation: `8f17338ae974243d4096919f3e4da097605804b4`;
- exact qualification hardening/final source: `7400cad6531b2687ffb150959cbf534c6797359e`;
- clean worktree: `/tmp/backtest-a-share-daily-bundle-clean`;
- clean focused authority/projection: 63 passed;
- broad Tushare/G12A/B/C/D/G/publication: 93 passed;
- full repository: 1846 passed;
- import boundaries: 113 files passed;
- final independent review: `NONE`;
- event hash: `sha256:ab872662754a286bf9f41e722e739fe8f961d387d4d6cfa95e13888e0c8e8b0f`;
- stream content hash: `sha256:27bb8945601e9a869e609bb8c146a998fca06878061950f294c2a0dabacd426c`;
- manifest content hash: `sha256:7d87625e9fce5b3f668a8f1ba9a3e302a09dc334b28b61760a8212a6818f80fc`;
- manifest hash: `sha256:f343a0d9e4d86659ad0b1c73c888d050886f9713acedc77fc31fc16202fbce3f`;
- retention proof hash: `sha256:77ce91f2cc959c6f8584da4d3844f436cb241b0060ed6d2e77c2f7dd2164a492`.

This does not make G12L/listing, provider revision closure, corporate actions,
G12I, G12K, G12M, decision grade, or deployment ready.
