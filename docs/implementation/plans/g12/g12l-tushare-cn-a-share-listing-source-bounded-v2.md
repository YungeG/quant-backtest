---
id: G12L-TUSHARE-CN-A-SHARE-LISTING-SOURCE-BOUNDED-V2
readiness: ACCEPTED_SOURCE_BOUNDED_SLICE
status: ACCEPTED
gate_status: PASSED
owner: Backtest tools/acquisition + market-bundle-builder source observation
depends_on:
  contract: [G12A, G12L-TUSHARE-CN-A-SHARE-DAILY-LISTING-V1, G12CD-TUSHARE-CN-A-SHARE-DAILY-PUBLICATION-V2, ADR-0010]
  evidence:
    - stock_basic sha256:8922c3e8764f8c1223e28ed785f97dadecd4b6fee7399a6210c03dbb616abaae
    - bak_basic sha256:38be7fdfb008fd015a939191c37279e328deef366f7a57293403654655057490
    - namechange sha256:e61ae5499dd8293509df9da1752ea080958e1f3d3c9a70fe713c8740fdb9a881
---

# G12L Tushare fixed-singleton listing source-bounded v2

## Status and purpose

D1-D3 `PASSED` at acquisition-tool implementation
`f140e8efef90fa41b4847eb67b93f1e68304e126`, exact evidence commit
`5c0311bcc793d10bfe2b301ed8cc317b8846a9da`, and observer implementation
`dc8b1fb35115b61f951cd69df79e46c4c1057a8f`. The accepted report is
`sha256:6d120c94b8d08fa00389d91894bc17d18ad4a6e0c1f9c42b859e7f1e26cc41c8`.
Focused/adjacent validation passed 38 tests, full-repository validation passed
2403 tests, the 135-file import boundary passed, and independent review returned
`PASS`.

This acceptance is only the exact source-bounded statement below. It does not
upgrade the historical v1 listing/lifecycle gate or authorize decision grade,
live eligibility, or deployment.

## Outcome

Add one exact fixed-singleton source-bounded successor for `000001.SZ` and provider
date `20240102`. It may state only that, at the recorded acquisition time, Tushare
through the ADR-0010 approved transport returned:

1. one current listed identity row;
2. one `bak_basic` historical daily-list row for the target date; and
3. exactly one returned name interval covering the target date.

The historical v1 listing/lifecycle gate remains blocked. The successor does not
claim uninterrupted listing, provider/exchange completeness, authoritative absence,
revision finality, survivorship safety, corporate-action lifecycle, decision grade,
live use, or deployment.

Research authority:
[`tushare-cn-a-share-listing-history-primary-sources.md`](../../../research/tushare-cn-a-share-listing-history-primary-sources.md).
Transport authority: [ADR 0010](../../../adr/0010-xiaodefa-is-approved-tushare-transport-proxy.md).

## D1 — exact transport and request contract

The sole acquisition interface is:

```text
TushareListingSourceBoundedRequestV2(ts_code, trade_date)

acquire_tushare_listing_source_bounded_v2(
  request,
  *,
  token,
  endpoint,
  output_dir,
  acquired_at_epoch_nanoseconds,
  post,
  sleep,
) -> receipt mapping
```

Fixed scope:

```text
provider: tushare.pro
transport_proxy: xiaodefa.approved-tushare-proxy.v1
instrument: 000001.SZ / xshe:000001
trade_date: 20240102
primary endpoint: https://fast.xiaodefa.cn
accepted alternate endpoint: https://tt.xiaodefa.cn
```

Exact calls, in order:

```text
stock_basic(
  ts_code=000001.SZ,
  list_status=L,
  fields=ts_code,symbol,name,market,exchange,list_status,list_date,delist_date,
)

bak_basic(
  trade_date=20240102,
  ts_code=000001.SZ,
  fields=trade_date,ts_code,name,list_date,
)

namechange(
  ts_code=000001.SZ,
  fields=ts_code,name,start_date,end_date,ann_date,change_reason,
)
```

Every request is `POST /` with token-free canonical key-sorted JSON,
`Accept-Encoding: gzip`, and the exact 56-character credential only in `x-api-key`.
Redirects are disabled and 3xx fails without retry. Calls are separated by at least
0.5 seconds. Transport/invalid-gzip/429/5xx failures use at most three attempts;
provider business errors do not retry. One capture never switches endpoint.

## D2 — acquisition evidence

The no-clobber output contains exactly:

```text
stock-basic.json
bak-basic.json
namechange.json
acquisition-receipt.json
```

Success requires exact unique-key Tushare envelopes, exact field order, terminal
`has_more=false` with observed integer `count=0`, one current row, one target-date
historical row, valid unique name intervals, and one covering interval. Current,
historical, and covering-name rows must agree on code, name, and listing date where
represented.

The receipt binds provider, transport key, exact endpoint, request scopes, auth mode,
attempts, response byte counts/local SHA-256s/row counts, one three-member G12A
Snapshot, and all qualification flags false, including `absence_authority=false`. The
credential is absent from every output and failure. Existing output is never replaced
and any ordinary pre-publication exception leaves no output directory. The inherited
cooperative local-filesystem publisher is receipt-last/no-clobber but does not claim
recovery from abrupt process death; a directory without the final receipt is invalid
and must be discarded before a new capture.

D2 write set:

```text
tools/acquisition/cn_a_share_tushare_listing_source_bounded_v2.py
tests/tools/acquisition/test_cn_a_share_tushare_listing_source_bounded_v2.py
tests/architecture/test_g12l_tushare_listing_source_bounded_v2_boundary.py
docs/adr/0010-xiaodefa-is-approved-tushare-transport-proxy.md
this plan
```

## D3 — source-bounded observer

After an operator-authorized credential produces accepted exact bytes, add one
off-root pure Builder observer with only:

```text
TushareCnAShareListingSourceBoundedObservationReportV2
TushareCnAShareListingSourceBoundedObservationOutcomeV2
observe_tushare_cn_a_share_listing_source_bounded_v2(...)
```

It deep-reconstructs the receipt, Snapshot, three responses, and accepted G12CD v2
catalog identity; recomputes all source-row and report identities; verifies the
fixed statement above; supports append-only direct supersession; and returns exactly
one report or one structured failure. It performs no network/filesystem I/O and
imports no Runtime or Trading Kernel.

Top-level failure precedence:

1. `INVALID_INPUT`;
2. `EVIDENCE_INVALID`;
3. `REQUEST_SCOPE_MISMATCH`;
4. `RESPONSE_SCHEMA_MISMATCH`;
5. `RESPONSE_PAGE_INCOMPLETE`;
6. `SOURCE_OBSERVATION_CONFLICT`;
7. `REPORT_BINDING_MISMATCH`.

D3 write set:

```text
packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_listing_source_bounded_v2.py
tests/bundle_builder/providers/tushare/test_cn_a_share_listing_source_bounded_v2.py
tests/architecture/test_g12l_tushare_listing_source_bounded_v2_observer_boundary.py
tests/fixtures/market_data/providers/tushare/g12l-listing-source-bounded-v2/observation-report.expected.json
this plan
```

## Acceptance

D2 acceptance runs the focused acquisition and architecture tests, existing Tushare
acquisition compatibility tests, import boundaries, LSP/lens, lock/diff/compile, and
gitleaks. D3 additionally freezes exact real fixture/report hashes and runs focused,
adjacent, full-repository, and independent review gates.

The live capture used the sole operator-authorized credential after the operator
explicitly accepted its prior chat exposure as the active credential. The credential
remains outside source control, fixtures, receipts, reports, logs, and provenance.
That operational exception does not elevate any completeness, lifecycle,
decision-grade, live-eligibility, or deployment qualification.

Accepted identities:

```text
receipt file: sha256:fd2935816572c02773cef3fa5c3141a9db033fce4ebe3e70b91b4ac710550ba7
snapshot: sha256:3144690c004ea0b8a727d33943e47c00cecd257bf8c142f15982d70f745c25e8
request scope: sha256:aaa6995714b99510137c667783d272010c848c40aa2ac4a359b6de04a4ac3dd0
instrument catalog: sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc
report: sha256:6d120c94b8d08fa00389d91894bc17d18ad4a6e0c1f9c42b859e7f1e26cc41c8
report file: sha256:24122b0a68c87f7bdc5723640724733a2d1f25a7c1b62b0f02eb17bdad2d0205
```
