# G12H live-status API probes v1

## Result

Target: `2026-07-30T16:00:00Z` for XSHE domestic ordinary A-share trade-notional charges.

**F1 remains blocked.** The bounded post-ADR-0006 search found a machine-readable SZSE current-document selector and confirmed that STA does not classify Announcement 2023 No.39 under any published legal-aging status. Neither result supplies an explicit nonblank live status, so neither qualifies for receipt-time substitution under ADR 0006.

This phase is additive. Wave 1, register-discovery evidence, PASSED artifacts, APIs, fixtures, hashes, and identities remain unchanged.

| Artifact | Frozen value |
|---|---|
| Official HTTP packages | 9 HTTP 200 packages |
| Evidence files | 99 files; root ledger has 98 entries and excludes itself |
| Manifest | `evidence/g12h-live-status-api-probes-v1/manifest.json`; `sha256:cb1b868fc7ce63fb9b82e379385f832dd6184b97de3f48b0a177c0a65899342c` |
| Ledger | `evidence/g12h-live-status-api-probes-v1/sha256sums.txt`; `sha256:04714734fcdef8e424281f7492ea0cdf1a6d8cff8d07f06c52489a4d2639d30a` |
| Assessment | `evidence/g12h-live-status-api-probes-v1/analysis/live-status-api-probe-assessment.json`; `sha256:cf1b6b25192dd83652af8b96aca0424082fd3e22afd1a11cceaa585a67be80cf` |
| Operator manifest | `evidence/g12h-live-status-api-probes-v1/operator/manifest.json`; `sha256:b891675094feb3ebcb4da3e51647e520dcd492fd8085ac4415cd02494834ee0d` |
| Private-header receipt | `evidence/g12h-live-status-api-probes-v1/private-response-header-store-receipt.json`; `sha256:33d7b5cc81e5d173369c5e3f950ace7a80c2b4fe3ed7a8b3286e637f48856037` |

Exact transient-cookie-bearing response bytes are retained mode-restricted at `/srv/bcache-8t/ygguo/backtest/g12h-authority-private/20260820-live-status-api-probes-response-headers`; private manifest `sha256:7a19a80f03ee5364a6487252a918a68829701d642a48c112a54f673bcf2d2bdc`.

## SZSE current-document API

Captured official endpoints:

```text
GET https://www.szse.cn/marketServices/deal/payFees/index.json
GET https://www.szse.cn/marketServices/deal/payFees/t20251231_618209.json
GET https://www.szse.cn/marketServices/deal/payFees/t20251231_618209.html
```

The unversioned selector returned exactly one current candidate and pointed to the captured document paths. The selected document identifies `docId=618209`, publication time `1767144191000`, the January-2026 fee schedule, A-share handling fee `0.0341‰` bilateral, securities regulatory fee `0.02‰` bilateral, and `代中国证监会收取`.

This is stronger exact endpoint and content identity, but not a qualifying ADR-0006 status result:

- `code=0` and `message=成功` mean request success;
- selector and document both return `docTitleStatusTime=""`;
- no effective, active, amended, repealed, superseded, or successor field exists;
- no complete fee-table amendment/repeal/correction corpus is declared.

Disposition: `CURRENT_DOCUMENT_SELECTOR_CONFIRMED_STATUS_UNDECLARED`; `exchange_handling` and the SZSE collection side of `securities_regulatory` remain insufficient.

## STA No.39 status-filter matrix

The exact No.39 query was captured unfiltered and with every status exposed by the official STA UI:

```text
全文有效
已修改
全文失效
全文废止
尚未生效
```

Results are deterministic:

- unfiltered: `total=1`, exact `财政部 税务总局公告2023年第39号`, with `xxgk_aging=""`, `xxgk_abolishDate=""`, and `xxgk_reviseType=""`;
- each of the five status-filtered queries: `status=1000`, `total=0`, no result rows;
- unfiltered aggregation: `agingList=[{"doc_count":1,"key":""}]`.

`status=1000` is search-service success, not document validity. The matrix proves only that STA currently leaves No.39 unclassified under every published legal-aging status. It does not prove effective, amended, repealed, or unchanged state.

Disposition: `NO39_EXPLICITLY_UNCLASSIFIED_ACROSS_PUBLISHED_STATUS_FILTERS`; `stamp_duty` remains insufficient despite the separately qualifying NPC Stamp Duty Law `sxx=3` result.

## Remaining lineages

The bounded endpoint search found no qualifying official live-status API, immutable as-of selector, or declared complete successor map for:

- ChinaClear Shenzhen-market fee-standard tables;
- HKSCC clean Definitions and Section 21;
- NDRC/MOF 2018 No.917 and the complete regulatory-fee lineage.

Current pages, mutable PDFs, `Last-Modified`, publication dates, JSON current-document selectors without explicit status, and search/list termination remain insufficient under ADR 0006.

## Boundary

No common `official_record_as_of` is set. No closure artifact, RuleBook, F2 projection, F3 publication, analyzer work, or qualification is authorized.

A positive next step requires either an explicit nonblank issuer-owned official live-status API response for each remaining exact act/table together with complete candidate channels, or issuer-authenticated archive/status certificates. No broader receipt-time or current-page relaxation is implied.
