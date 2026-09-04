# G12H XSHE Domestic Ordinary: Wave 1 capture result v1

## Result

Wave 1 and bounded discovery captures are complete for the frozen scope `Asia/Shanghai [2026-07-06, 2026-07-31)`, XSHE, equity, CNY, auction, domestic access, ordinary A share, trade-notional charges.

**Authority remains INSUFFICIENT.** This result authorizes no rate, applicability result, `official_record_as_of`, `closure_evidence_available_at`, successor/correction relation, RuleBook entry, F2 projection, F3 publication, analyzer implementation, or qualification.

## Immutable capture set

| Item | Result |
|---|---|
| Bound execution scope | `PASS_SCOPE_ONLY_AUTHORITY_INSUFFICIENT`; `evidence/g12h/scope/receipt.json`; `sha256:08a0913c6955eea4f63cce9de0c6a9cf71aea5333cd29b5c2ce2ab0b089fb944` |
| Official HTTP source packages | 151 packages: 150 HTTP 200 captures and one expected out-of-range ChinaClear HTTP 302 terminal capture |
| Evidence tree | 1,574 files, approximately 46 MiB |
| Wave 1 manifest | `evidence/g12h/wave1-manifest.json`; `sha256:b54a3e34eb2aa9896306c48c9b3e971dff241dc97c282bc3fdf99b2616dcbe9c` |
| Evidence checksum ledger | `evidence/g12h/wave1-sha256sums.txt`; `sha256:e57d89fb96ceba34d36c545e7c514d19a1588f9cb6e4da1d5c7110fe7979a610` |
| Operator source manifest | `evidence/g12h/operator/manifest.json`; `sha256:f287c2585eb7a5d642297afa8b42f6167111f9786363958fe08dd76f8ad5b7d7` |
| Executed acquisition schedule | 151 request packages; `evidence/g12h/operator/executed-acquisition-schedule.json`; `sha256:ed84ba4e2f0163125ab89e8668a24027211506e2c0bb181befe372ab31b2c5f1` |
| Cutoff receipt | `INSUFFICIENT_NO_COMMON_OFFICIAL_RECORD_AS_OF`; `evidence/g12h/cutoffs/receipt.json`; `sha256:a7f7952052885532254d5898c6aaf9c1ca1e8d196d858b1e723d83834f7eb622` |

Every source package retains the request, response chain, response metadata, raw body or terminal response, deterministic extraction where applicable, receipt, and SHA-256 ledger. The three captured PDFs were rendered in full: ChinaClear Shenzhen fee table 10 pages, HKSCC §21 25 pages, and HKSCC Definitions 42 pages. The Stamp Duty Law's linked original rate-schedule PPT was also captured (`sha256:60ef5ae1dfb9631d84ee09247748ca292a4c81cb995a47aa0fab89206ee5aa64`); rendering is explicitly unavailable because no PPT renderer is installed.

## Lineage results

| Lineage | Captured evidence | Result and remaining blocker |
|---|---|---|
| `exchange_handling` | Current SZSE fee table; 2023 No. 768 HTML and JSON; current general-notice pages declared by the captured index; keyword search page and terminal page | The current index yielded 320 notice entries through 2026-08-14. The exact `交易经手费` search yielded only three records and terminated, with No. 768 the newest. The fee table remains labelled 2026-01. Neither channel is issuer-declared as a complete fee-table successor/correction register, so no post-target fee record state is qualified. |
| `securities_regulatory` | NDRC 2018 No. 917, 2021 No. 1947, document-library protocol, four exact query sets and terminal pages; separate SZSE collection-table capture | Six unique NDRC candidates were preserved; the newest is 2022-01-07. All competent-rate candidates are pre-target, and the search corpus is discovery rather than a complete amendment/repeal register. The separate SZSE collection table remains labelled 2026-01. Both regulatory streams remain open. |
| `chinaclear_transfer` | Fee-table parent/iframe/page script, 10-page Shenzhen fee PDF, 2022 reduction notice, current notice index pages 1–55, and out-of-range terminal response | The issuer script declared 55 pages and 1,082 records; all were captured. Twenty-two titles matched broad fee keywords. No post-target stock-transfer-fee act was located: the latest broad fee title is a 2025 bond-fee notice, while the stock-transfer candidate remains the 2022 reduction notice. The notice corpus is not declared as a complete transfer-fee successor/correction register. |
| `hkscc_transfer` | Operational Procedures index, §21, Definitions, formal rule-update index, HKSCC circular form schema, all load-more responses for 2025-09-01 through 2026-08-31, and terminal empty response | The bounded circular range produced 459 unique candidates and terminated at `currentcount=520`; the latest visible date is 2026-08-20. No circular title concerned transfer-fee, fee, charge, or Operational Procedures succession; broad keyword matches were mainly China Connect stock-admission/discontinuation records. Absence of such titles is not closure. The formal OP index and captured §21/Definitions versions remain source-dated in 2025, so the domestic conditional `applies=false` is still unqualified and never becomes a zero rate. |
| `stamp_duty` | STA-hosted Stamp Duty Law, its linked original rate-schedule PPT, and Announcement 2023 No. 39; gov.cn representation; exact No. 39 search schema/result; three subject-search sets with terminal pages | The exact No. 39 search returned one matching policy record. The three subject searches terminated at declared totals 14, 116, and 5, producing 127 unique broad candidates; the newest is 2025-10-15 and is not a post-target competent status record. `全文有效` on the live Law page has no qualified as-of date. No competent complete legislative/policy history register was found. |

Discovery inventories remain explicitly unresolved:

- `evidence/g12h/exchange_handling/candidate-inventory.discovery.json`
- `evidence/g12h/securities_regulatory/candidate-inventory.discovery.json`
- `evidence/g12h/chinaclear_transfer/candidate-inventory.discovery.json`
- `evidence/g12h/hkscc_transfer/candidate-inventory.discovery.json`
- `evidence/g12h/stamp_duty/candidate-inventory.discovery.json`

## Secret-safe exact-byte handling

Public HTTP responses issued transient session/WAF cookies. Exact cookie-bearing response-header, redirect, and transport bytes are retained outside Git in a mode-restricted store; Git-tracked copies retain cookie names and attributes but replace values with SHA-256.

- public receipt: `evidence/g12h/private-response-header-store-receipt.json`
- public receipt hash: `sha256:cbc841725fe92d7e1c7660453ec1d7d743a41e9a496a87e11771ee5d83354911`
- private manifest hash: `sha256:4cb9879039ca9ed9d5582e23013557099253bcbf1c0bde709d9b0e0ccbcdef05`

One exact NDRC HTML response embeds a public client-side search key that triggers generic secret scanning. Its exact bytes are likewise retained in a separate mode-restricted store, while the tracked copy replaces only that key literal with its SHA-256.

- public receipt: `evidence/g12h/scanner-sensitive-exact-byte-store-receipt.json`
- public receipt hash: `sha256:b2e9b00aca07d663c5f84cd4275531859a0e7ef69ad494ab0666ed46814c2f05`
- private manifest hash: `sha256:a911cda6040039aa85b2630448d343da6d809f6a06779c34d4ca1f79975fb37e`

No user credential, API credential, request cookie, authorization header, or secret was used.

## Stop decision

A common `official_record_as_of` cannot be selected. Each economic lineage still lacks a competent, source-declared post-target record state and/or an issuer-declared complete successor/correction/repeal register. HTML rendered-DOM capture is also unavailable in the current acquisition environment; exact server HTML and deterministic text extractions were retained instead.

The next bounded action is not broader history collection. It is to locate or obtain the competent issuer-declared status/history register for each remaining lineage, then capture only the directly necessary predecessor relation and disposition the already frozen candidate set. Until that evidence exists, all candidate economics remain research observations only.
