# G12H XSHE Domestic Ordinary: latest-source capture plan v1

## Purpose and hard gate

This plan acquires the evidence required to evaluate charges for the frozen scope:

- `Asia/Shanghai [2026-07-06, 2026-07-31)`
- XSHE; `InstrumentType.EQUITY`; CNY quote and settlement; `AUCTION`
- all profile-admitted boards; `DOMESTIC`; `ORDINARY_A_SHARE`; `trade_notional`

It is a capture plan, not a RuleBook result. **No RuleBook entry, rate projection, `official_record_as_of`, `closure_evidence_available_at`, or lineage closure is authorized** until the relevant issuer-owned post-target record state, complete successor/correction inventory, scope proof, immutable captures, and candidate dispositions below are all present. In particular, HTTP `Date`/`Last-Modified`, retrieval time, a currently linked page, and absence of keyword hits are not official record-state or continuity proof.

Target-end cutoff: any qualifying `official_record_as_of` must be no earlier than **2026-07-30T16:00:00Z** (2026-07-31 00:00:00+08:00), and must satisfy:

```text
target_to_exclusive <= official_record_as_of <= closure_evidence_available_at
```

All currently investigated lineages are **INSUFFICIENT**. Where a producer or verifier did not provide coverage, this plan records it as missing rather than inferring it.

## Common capture package and acceptance rules

For every fetched representation, create a stable source identifier and retain, without overwriting prior retrievals:

- request method, URL, query/form body, request headers (with secrets redacted only in the manifest), response status/headers, content encoding, final URL, and full redirect chain;
- UTC retrieval receipt time, operator/tool/version, TLS/transport observations where available, and source-declared document/publication/effective/version dates as separate fields;
- exact raw response bytes; separately captured rendered DOM/table or PDF page renders where applicable; every linked/relevant attachment; and separately derived text extraction;
- SHA-256 for raw bytes, rendered derivative, each attachment, and extraction. Record byte length and MIME type beside every digest;
- a capture manifest that relates representations without asserting `corrects_revision_id`, duplication, amendment, repeal, or economic succession unless an official source expressly says so.

Suggested layout (names may add a retrieval nonce, never replace the stated artifact classes):

```text
evidence/g12h/<lineage>/<source-id>/request.json
evidence/g12h/<lineage>/<source-id>/response.headers
evidence/g12h/<lineage>/<source-id>/redirects.json
evidence/g12h/<lineage>/<source-id>/raw.{html,json,pdf,bin}
evidence/g12h/<lineage>/<source-id>/rendered.{html,pdf,png}
evidence/g12h/<lineage>/<source-id>/extracted.txt
evidence/g12h/<lineage>/<source-id>/attachments/<name>
evidence/g12h/<lineage>/<source-id>/receipt.json
evidence/g12h/<lineage>/<source-id>/sha256sums.txt
evidence/g12h/<lineage>/inventory.{json,csv}
```

A discovery search may terminate its own result set, but it cannot establish legal continuity unless the issuer expressly identifies it as the complete relevant amendment/repeal/correction/successor register. Preserve all candidate records—including irrelevant dispositions—so later closure is auditable. A missing complete channel, missing post-target dated record, missing complete frozen-scope proof, or fetch failure is a stop condition, not a reason to extrapolate a candidate rate.

### Frozen execution-scope binding — required before lineage acquisition

Create and hash `evidence/g12h/scope/bound-execution-scope.json` before any date-bounded official request. This is the sole cross-lineage scope source; it is an immutable, target-specific export of the V2B Runtime binding, not a fee-source substitute. Its receipt must name the producing Git object `5cbc3da58293d16571c662a1f1d2158f3c0f0017`, the accepted V2C fixture `tests/fixtures/kernel/profiles/cn_a_share/commission-tax-v2.json` (`sha256:5f0241887237a568f411a7d4a664482848ee134202d930903404aaf367f463e0`), the immutable ADR binding `docs/adr/0005-cn-a-share-fees-require-access-route-and-product-class.md` (`sha256:2ae3cb57ecb3e313445225ea5b1421a4d36a0c8ebbd5e5130c100c94c92e14b1`), and the actual profile declaration snapshot/manifest hashes. It must contain the exact target bounds and these field/value/source assignments:

| Frozen field | Required value | Proving authority/artifact |
|---|---|---|
| venue, instrument type, quote and settlement currency, mechanism | `XSHE`, `EQUITY`, `CNY`, `CNY`, `AUCTION` | canonical `CnAShareFeeExecutionScopeV2` export in `bound-execution-scope.json`, verified against the named V2C fixture and V2B producer commit |
| access route, product class | `DOMESTIC`, `ORDINARY_A_SHARE` | canonical Scope/Selection export plus ADR-0005 digest above |
| all admitted boards | canonical, finite board IDs from the bound profile's `CnAShareInstrumentRuleContext`; no inferred board set | target-specific immutable `CnAShareInstrumentScopeDeclaration` snapshot and manifest named in the export |
| domestic cash account and exclusions | domestic/cash true; Stock Connect, margin/short, and available-margin authorization false | target-specific immutable `CnAShareAccountScopeDeclaration` snapshot and manifest named in the export |
| ordinary A share and standard cash auction | true; B/H, fund/bond, restricted/pre-IPO, lending/repo, pledge/freeze, differential/self-distribution exclusions false | target-specific immutable instrument declaration snapshot and manifest named in the export |
| calculation basis | `trade_notional` | each lineage's competent official economic act/table; the bound export only binds that every selected act must match it |

The receipt records `bound_scope_sha256`, profile/instrument/account declaration hashes, board-ID tuple hash, producer commit, fixture hash, ADR hash, and verification result. Any absent export, hash mismatch, non-finite board tuple, or target/profile coverage mismatch stops **every** lineage as `INSUFFICIENT`; it may not be replaced by “A股” wording.

### Cutoff selection and date-range receipt

After Wave 1 discovery and before any Wave 2 date-bounded enumeration, create `evidence/g12h/cutoffs/receipt.json`. For every lineage (and both regulatory streams), record the earliest competent, source-declared record state at or after `2026-07-30T16:00:00Z`, its source ID, and its record-state proof. Set the single `official_record_as_of` to the latest of those recorded instants, so every component has a qualified state no later than the common as-of time. Then set each channel's `query_end_local_date` to the local calendar date containing that common instant, record whether that UI's `DateTo` is inclusive, and use that inclusive date (or its documented exclusive equivalent). Only after all candidate pages through every frozen query end are captured may the operator set `closure_evidence_available_at` to the UTC receipt time of the final terminal request. The receipt fields are `target_to_exclusive`, `lineage_record_states` (lineage/stream, source ref, source-declared time, proof), `official_record_as_of`, `query_start_local_date`, per-channel `query_end_local_date` and `ui_end_semantics`, `final_terminal_source_ref`, `final_terminal_retrieved_at`, and `closure_evidence_available_at`; validation requires `target_to_exclusive <= official_record_as_of <= closure_evidence_available_at`. If any lineage lacks a qualified record state or any channel lacks a documented date-bound conversion, stop before inventory qualification.

### Candidate-disposition inventory

For each ordered candidate, `inventory.json` must contain `candidate_id`, `source_ref` (immutable source ID and SHA-256), issuer/authority, title, official act/revision ID if stated, published/recorded/effective dates, query/range provenance, full-scope comparison, explicit documentary relation/ref, explicit economic-predecessor relation/ref, and exactly one disposition: `no_effect`, `outside_scope`, `before_target_already_in_chain`, `after_target`, `documentary_correction_without_economic_change`, `target_affecting_correction_or_successor`, `repeal_without_replacement`, or `unresolved`. `no_effect` and `outside_scope` require a stated economic/scope comparison; correction/successor/repeal require the official relation source ref. Missing relation, effect classification, or source ref is `unresolved` and fails closed.

## Prioritized execution waves

1. **Wave 1 — latest endpoint bytes.** Capture all listed latest/live representations and their link contexts exactly as returned, including raw/rendered/attachment derivatives and receipts. Do not call any one of them verified “latest/current” merely because it is issuer-hosted or live.
2. **Wave 2 — cutoff then complete index termination.** Follow the cutoff receipt sequence above: qualify and freeze a competent record state first, freeze each UI date conversion/query end, then exhaust its stated range, pagination/cursors, amendment index, and attachments. Preserve totals and the explicit terminal empty/final response. If only a pre-target index is available, record that bounded fact and stop closure work for that lineage.
3. **Wave 3 — only necessary predecessor bytes.** Fetch only the minimal acts identified below when they supply a target-state field absent from the latest representation or an expressly required predecessor relation. Do not collect broad rate history.
4. **Wave 4 — candidate disposition.** Create the ordered inventory schema above through the frozen cutoff. Closure is possible only when every candidate has a sourced, deterministic disposition and all selected predecessor links are explicit.

## Lineage: exchange_handling

### Requirement matrix

| Requirement | Status | Capture/decision needed |
|---|---|---|
| Competent issuer, rate, `trade_notional`, both sides, start | Satisfied candidate evidence | Preserve 768 and table representations. |
| XSHE/EQUITY ordinary A-share candidate | Partial/satisfied only for A-share standard row | Preserve adjacent table rows, including block-trade distinction. |
| CNY, `AUCTION`, all admitted boards, `DOMESTIC`, `ORDINARY_A_SHARE`, complete tuple | Ambiguous | Use the frozen execution-scope binding above for XSHE/EQUITY/CNY/AUCTION/boards/DOMESTIC/ORDINARY_A_SHARE and preserve competent official act/table evidence for `trade_notional`; do not infer from “A股.” |
| Immediate predecessor act | Missing | The authoritative revision/register channel must identify the exact immediate predecessor act and cite the official relation. Fetch that single act and relation source if identified; if identity/relation is absent, stop rather than treating 768's prior-rate recital as a complete chain. |
| Post-target official record state | Missing | Acquire dated table/validity/revision record at or after cutoff. |
| Complete correction/successor channel and terminal representation | Missing | Obtain SZSE-declared complete channel and range termination; keyword search is discovery only. |
| Immutable evidence | Missing | Complete common capture package. |


### Located official representations (not verified latest/current)

| Representation | Exact official document and URL | What it supports | Limitation |
|---|---|---|---|
| Fee table | SZSE, **深交所收费及代收税费标准（2026年1月）** — <https://www.szse.cn/marketServices/deal/payFees/index.html> | A-share row: `0.0341‰`, by transaction amount, bilateral; visible label is 2026-01. | Mutable HTML; observed 2026-06-13 `Last-Modified` is transport metadata only and precedes target end. No terminal version/correction relation. |
| Transition act | SZSE, **关于下调股票交易经手费收费标准的通知（深证上〔2023〕768号）** — <https://www.szse.cn/disclosure/notice/general/t20230818_602805.html> and parallel <https://www.szse.cn/disclosure/notice/general/t20230818_602805.json> | Published 2023-08-18; effective 2023-08-28; changes A/B share bilateral handling fee from `0.0487‰` to `0.0341‰` by transaction amount. | Pre-target; HTML/JSON relationship is unproven until representation comparison; no correction/successor chain. |

### Minimal history

Capture **深证上〔2023〕768号** now. It is not sufficient to close the predecessor chain: the authoritative revision/register channel must supply the exact identity and official relation of the `0.0487‰` predecessor. Fetch only that identified predecessor and relation source—not a broader history. If the channel cannot identify it, preserve that failure and stop as `PREDECESSOR_EVIDENCE_MISSING`.

### Exact endpoints and termination

- `GET https://www.szse.cn/marketServices/deal/payFees/index.html`: retain raw HTML, rendered DOM/table, visible label/version metadata, linked attachment inventory, and distinct raw/rendered hashes.
- `GET https://www.szse.cn/disclosure/notice/general/t20230818_602805.html` and `GET https://www.szse.cn/disclosure/notice/general/t20230818_602805.json`: retain as separate source IDs; compare text and metadata before any duplicate/correction classification.
- Discovery only: `POST https://www.szse.cn/api/search/content`, form-encoded `keyword=交易经手费&time=0&range=title&channelCode[]=general_news&currentPage=N&pageSize=50`. The observed query had `totalSize=3` at page 1 and empty data at page 2. Retain all pages, totals, and terminal result, but never treat this keyword result as successor closure.
- **Acquisition blocker — SZSE complete channel.** Fetch `GET https://www.szse.cn/disclosure/notice/general/index.html` and `GET https://www.szse.cn/marketServices/deal/payFees/index.html`; capture raw HTML/scripts/link inventories and inspect only their issuer-linked API/form actions for a declared fee-table history, validity, repeal, correction, or successor register. For each discovered action, preserve the exact method, field names/defaults, response total, and pagination rule, then enumerate monotonically from its documented first page to its documented terminal page/empty response using the frozen cutoff receipt. If neither page supplies an issuer-declared complete channel and protocol, record both source IDs and stop `INSUFFICIENT`; the known keyword POST is discovery only and cannot be promoted to closure.

### Expected artifacts and stop conditions

Artifacts: fee table raw/rendered/extracted; 768 HTML/JSON raw/rendered/extracted; notice-search request/responses; table/version index and attachments; receipts and SHA-256 manifest.

Stop as **INSUFFICIENT** if no post-target record, declared complete channel, terminal documentary relation, or complete execution-tuple proof is found. The `0.0341‰` bilateral candidate must not be projected into July 2026.

## Lineage: securities_regulatory

This has two non-interchangeable streams: NDRC/MOF controls the exchange-charged regulatory-fee standard; SZSE supplies the investor-facing bilateral collection representation on behalf of CSRC. Equal `0.02‰` values do not prove correction, succession, or a complete execution charge.

### Requirement matrix

| Requirement | Status | Capture/decision needed |
|---|---|---|
| Controlling rate, act, basis, effective date | Satisfied candidate evidence | Capture 917. |
| Explicit predecessor disposition | Satisfied | 917 expressly abolishes 2016 No.14; do not fetch 2016 No.14. |
| Investor-facing bilateral collection | Satisfied candidate evidence | Capture SZSE table separately. |
| Full frozen tuple | Ambiguous | Use the frozen execution-scope binding above for CNY, `AUCTION`, boards, `DOMESTIC`, ordinary class; preserve official act/table evidence for `trade_notional`. |
| Post-target endpoint for each stream | Missing | Acquire separate NDRC/MOF and SZSE qualified record states. |
| Complete successor/correction inventories, terminal relations, immutable evidence | Missing | Execute Waves 1–4 for both streams independently. |


### Located official representations (most recent candidates located; not verified latest/current)

| Stream | Document and URL | Candidate support | Limitation |
|---|---|---|---|
| Controlling rate | NDRC/MOF, **国家发展改革委 财政部关于证券期货业监管费标准等有关问题的通知（发改价格规〔2018〕917号）** — <https://www.ndrc.gov.cn/xxgk/zcfb/ghxwj/201806/t20180627_960950.html?code=> | `0.02‰` of stock transaction value; effective 2018-01-01; expressly abolishes 发改价格〔2016〕14号. | Pre-target; no captured successor/correction chain. |
| Later candidate | NDRC/MOF, **发改价格〔2021〕1947号** — <https://www.ndrc.gov.cn/xxgk/zcfb/tz/202201/t20220107_1311590.html> | Extends Shanghai/Shenzhen standard to Beijing; says standards may later be assessed/adjusted. | Later candidate requiring disposition, **not** an established XSHE successor to 917. |
| Collection | SZSE, **深交所收费及代收税费标准（2026年1月）** — <https://www.szse.cn/marketServices/deal/payFees/index.html> | `证券交易监管费/A股`: `0.02‰`, transaction amount, bilateral, collected for CSRC. | Pre-target mutable collection table; not a substitute for NDRC/MOF authority. |

### Minimal history

Fetch **917** and the SZSE collection table. Inventory **1947** as a later candidate requiring disposition, but do not call it necessary predecessor or successor. Do not fetch **发改价格〔2016〕14号**, already expressly abolished by 917.

### Exact endpoints and termination

- NDRC document library discovery page: <https://www.ndrc.gov.cn/xxgk/wjk/index.html?tab=all&qt=%E8%AF%81%E5%88%B8%E6%9C%9F%E8%B4%A7%E4%B8%9A%E7%9B%91%E7%AE%A1%E8%B4%B9>. Its first-party API is `GET https://fwfx.ndrc.gov.cn/api/query` with `qt`, `tab=all`, `page` (1-based), `pageSize=20`, `siteCode=bm04000fgk`, `key=CAB549A94CF659904A7D6B0E8FC8A7E9`, `startDateStr=1900-01-01`, `endDateStr=<query_end_local_date from cutoffs/receipt.json>`, `timeOption=2`, `sort=dateDesc`. Use each precise query `证券期货业监管费`, `证券业务监管费`, `证券交易监管费`, and `发改价格规〔2018〕917号`; retain page 1 through `ceil(total/20)` plus one terminal empty page, or fail on a total cap. These are discovery inventories only.
- `GET` 917 and 1947 URLs above; capture raw/rendered representations and every official linked correction/version/attachment relationship.
- `GET https://www.szse.cn/marketServices/deal/payFees/index.html`; optionally fetch linked fee-management PDF `http://docs.static.szse.cn/www/marketServices/deal/payFees/W020200228805325484325.pdf` **only** if it supplies version/revision or applicability facts.
- **Acquisition blocker — competent complete registers.** For NDRC/MOF, fetch the library page above and every issuer-linked “validity”, “amendment”, “repeal”, or “history” register link; for SZSE, use the two exact SZSE pages and discovery protocol in `exchange_handling`. A register qualifies only when its issuer states the covered authority/type/date range. Enumerate its declared first-to-terminal pagination with `endDateStr/query_end_local_date` from the cutoff receipt. Any undocumented coverage, missing register, or NDRC 500-result cap fails closure; never substitute “every relevant” register by operator judgement.

### Expected artifacts and stop conditions

Artifacts: two NDRC/MOF act captures, NDRC query pages, SZSE table raw/rendered, selected PDF if justified, both successor-channel inventories, attachments, receipts/digests.

Stop as **INSUFFICIENT** unless both distinct streams have post-target authoritative states and complete inventories. Do not conflate their propositions or use a vague “post-target” time in place of the exact cutoff.

## Lineage: chinaclear_transfer

### Requirement matrix

| Requirement | Status | Capture/decision needed |
|---|---|---|
| Competent issuer, rate, basis, bilateral sides, start/predecessor | Satisfied candidate evidence | Capture 2022 notice and full PDF. |
| XSHE/A-share candidate | Satisfied candidate evidence | Preserve full table and adjacent mechanism rows. |
| Full frozen tuple | Ambiguous | Use the frozen execution-scope binding above plus official table evidence for `trade_notional`; no auction inference from standard row. |
| Post-target state; successor/correction channel; terminal representation; immutable evidence | Missing | Obtain post-target ChinaClear endpoint and execute complete inventory/capture. |


### Located official representations (not verified latest/current)

| Representation | Exact official document and URL | Candidate support | Limitation |
|---|---|---|---|
| Fee index/table | ChinaClear **收费标准** parent <https://www.chinaclear.cn/zdjs/fbzyls/service_tlist.shtml>, iframe <https://www.chinaclear.cn/zdjs/fbzyls/service_tlist/code_0.shtml>, and **深圳市场证券登记结算业务收费及代收税费一览表** PDF <https://www.chinaclear.cn/zdjs/fbzyls/202512/a59388fbfa714c5fa546784891a42e30/files/%E6%B7%B1%E5%9C%B3%E5%B8%82%E5%9C%BA%E8%AF%81%E5%88%B8%E7%99%BB%E8%AE%B0%E7%BB%93%E7%AE%97%E4%B8%9A%E5%8A%A1%E6%94%B6%E8%B4%B9%E5%8F%8A%E4%BB%A3%E6%94%B6%E7%A8%8E%E8%B4%B9%E4%B8%80%E8%A7%88%E8%A1%A8.pdf> | Shenzhen A-share transfer fee `0.01‰` of transaction amount, charged to both parties; separate comprehensive-agreement-platform `0.007‰` row. | Index generation 2026-03-27 and PDF listing 2025-12-31 are pre-target. Platform distinction precludes mechanism inference. |
| Transition act | ChinaClear **中国结算关于降低股票交易过户费收费标准的通知** — <https://www.chinaclear.cn/zdjs/gszb/202204/837e3c5031104aa099d6597ba381342a.shtml> | Effective 2022-04-29: Shanghai/Shenzhen A-share fee reduced from `0.02‰` to `0.01‰`, bilateral, transaction amount. | Preserve distinct body date 2022-04-28 and conflicting metadata/page-generation 2023-05-08; neither is target closure. |

### Minimal history

Capture the 2022 reduction notice now. Its recital of a `0.02‰` prior state is not an exact predecessor authority: the post-target competent channel must identify the immediate predecessor act and the official economic relation. Fetch only that identified act and relation source—not broad pre-2022 history. If no identity/relation is supplied, stop as `PREDECESSOR_EVIDENCE_MISSING`.

### Exact endpoints and termination

- `GET` the parent and iframe index. Capture the iframe and referenced `page.js`. The embedded `newCreatePageHTML('page_div',1,1,'code_0','shtml',4)` declares page 1 of 1 and count 4; retain this declaration and verify no `_2` link is rendered. It terminates **only the 2026-03-27 pre-target inventory**.
- `GET` the exact PDF above as original bytes, render all 10 pages, extract/hash text independently, and retain headers/ETag/Last-Modified as transport facts only.
- `GET` the 2022 notice with raw/rendered data and all body/metadata dates preserved separately.
- **Acquisition blocker — ChinaClear candidate channel.** `GET https://www.chinaclear.cn/zdjs/xtzgg/center_flist.shtml`, its iframe(s), and referenced script(s); retain raw bytes before issuing any pagination request. Extract the issuer-supplied method, URL, field names/defaults, first page, page-size/total, and terminal rule. If these are absent, or the page does not declare a post-target complete notice/history scope, preserve the discovery captures and stop `INSUFFICIENT`. Otherwise enumerate exactly from declared first page through declared final/empty response, bounded by `official_record_as_of`, with every attachment retained.

### Expected artifacts and stop conditions

Artifacts: parent/iframe/page-script raw bytes; table PDF raw/renders/extraction; 2022 notice; post-target notice/table index; all candidates/attachments; receipts/digests.

Stop as **INSUFFICIENT** if the sole finite index remains pre-target, no complete post-target successor channel exists, or complete CNY/auction/boards/domestic/ordinary scope proof remains absent.

## Lineage: hkscc_transfer

ChinaClear and HKSCC are separate lineages and must never be economically blended. This lineage is about whether a separately defined China Connect charge applies, not a domestic “zero rate.”

### Requirement matrix

| Requirement | Status | Capture/decision needed |
|---|---|---|
| Competent charge predicate and definition | Satisfied candidate evidence, provenance capture pending | Capture index link context, PDFs and metadata. |
| DOMESTIC result | Conditional candidate `applies=false` | The official materials prove an exclusive China-Connect predicate. Combined with ADR-0005’s immutable execution-enforced `DOMESTIC` discriminator, this supports `applies=false`; ADR-0005 is not HKSCC authority, and **never conclude `rate=0`**. |
| Full tuple independently stated in HKSCC source | Ambiguous | Use the frozen execution-scope binding and its fixed ADR-0005 digest; retain the official exclusive China-Connect predicate and do not silently generalize. |
| Post-target §21/definition state; complete amendment/circular channel; terminal relations; immutable evidence | Missing | Capture and disposition all selected candidates through cutoff. |


### Located official representations (live/currently linked, not qualifying current endpoints)

| Representation | Exact official document and URL | Candidate support | Limitation |
|---|---|---|---|
| Charge section | HKSCC Operational Procedures §21 — <https://www.hkex.com.hk/-/media/HKEX-Market/Services/Rules-and-Forms-and-Fees/Rules/HKSCC/Operational-Procedures/SEC21.pdf> | §21.1A: `0.002%` of gross value, RMB on T, payable by a China Connect Clearing Participant for each China Connect Securities Trade cleared/settled through HKSCC. | Retained Last-Modified/PDF metadata are 2025-09; pre-target only. |
| Definition | HKSCC Operational Procedures Definitions — <https://www.hkex.com.hk/-/media/HKEX-Market/Services/Rules-and-Forms-and-Fees/Rules/HKSCC/Operational-Procedures/Definiti.pdf> | Defines China Connect Securities Trade as executed on a China Connect Market through an SEHK Subsidiary under a Trading Link. | Retained date 2025-07; pre-target only. |
| Amendment index | <https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Rules/HKSCC/Rules/Rule-Update_HKSCC-Operational-Procedures?sc_lang=en> | Formal OP update channel, visibly updated 2025-09-01. | Pre-target cutoff. |
| Candidate index | HKSCC circulars <https://www.hkex.com.hk/Services/Circulars-and-Notices/Participant-and-Members-Circulars?sc_lang=en&Category=HKSCC&DateFrom=2025-09-01&DateTo=2026-08-31> | Dated post-target candidate index (visible entries include 2026-08-18). | Not a dated §21/Definitions representation and not continuity proof until completely captured/dispositioned. |

### Minimal history

No historical rate act is necessary for domestic non-applicability. The 2015 fee-reduction PDF (`68-15-CCASSOP-NB-Fee-reduction`) is discovery-only and must not enter the chain unless a captured official candidate specifically requires disposition.

### Exact endpoints and termination

- `GET https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Rules/HKSCC/Operational-Procedures?sc_lang=en`; capture raw/rendered link inventory to prove source linkage, plus the exactly linked `SEC21.pdf` and `Definiti.pdf` original PDFs. Do not fetch `Whole_HKSCCOP_e.pdf` unless the captured index identifies a missing §21/Definitions version or amendment relation that those two PDFs cannot supply; then record that precise missing field and exact discovered URL.
- Extract the §21 transfer-fee note from `SEC21.pdf` and the China-Connect definition from `Definiti.pdf`; there is no separate, undefined “§21 continuation page” artifact.
- `GET` the formal amendment index; capture all linked clean/marked amendments needed by the candidate inventory. Its visible pre-target update does not close the chain.
- **Acquisition blocker — HKSCC circular form.** Initial request is `GET https://www.hkex.com.hk/Services/Circulars-and-Notices/Participant-and-Members-Circulars?sc_lang=en&Category=HKSCC&DateFrom=1900-01-01&DateTo=<query_end_local_date from cutoffs/receipt.json>` with empty keyword. Capture its raw HTML. The hidden field values are not assumed: extract their exact values for `pageUrl`, `TopicFieldName`, `DateFieldName`, `FilesFieldName`, `ImageFieldName`, `ContentFieldName`, `Category1FieldName`, `Category2FieldName`, `Category3FieldName`, `isCardView`, `tabItemSourceID`, `isHideDay`, and `urlHost` into the request receipt. Only then POST those exact values plus `Category=HKSCC`, empty keyword, frozen dates, `currentcount=20`, and `loadmorecount=20` to `https://www.hkex.com.hk/layouts/HKEX_Common/Tab/NewsCentreDetailsLoad.aspx/DisplayNewsCentreDetailsLoad`; increase `currentcount` by 20 per nonempty `result.d`, terminating only at null/empty `result.d`. Missing hidden values, changed schema, or no issuer-declared coverage is an acquisition blocker and stops `INSUFFICIENT`; retain every request/response and attachment.

### Expected artifacts and stop conditions

Artifacts: frozen execution-scope binding/receipt (including ADR-0005 path, digest, V2B commit, V2C fixture hash, and target-specific profile declaration hashes); OP index raw/rendered/link inventory; all selected original PDFs plus metadata/renders/extractions; rule update index/amendments; initial circular HTML, AJAX responses, attachments, candidate inventory; receipts/digests.

Stop as **INSUFFICIENT** if no post-target HKSCC-owned representation for both §21 and Definitions, no complete amendment/circular disposition, no provenance linkage, or no terminal correction chain. The only permitted provisional semantic is conditional `applies=false`, never a domestic transfer-fee rate of zero.

## Lineage: stamp_duty

### Requirement matrix

| Requirement | Status | Capture/decision needed |
|---|---|---|
| Statutory base, rate/basis/seller, effective/repeal | Satisfied candidate evidence | Capture Law including schedule. |
| Necessary half-collection successor | Satisfied candidate evidence | Capture No.39. |
| Documentary relation of STA/gov.cn No.39 representations | Ambiguous | Compare captured representations; leave relation unproven absent express official link. |
| Full frozen tuple | Ambiguous | Use the frozen execution-scope binding above for XSHE/EQUITY/CNY/AUCTION/boards/DOMESTIC/ORDINARY_A_SHARE and statutory acts for `trade_notional`, or fail closed. |
| Post-target status endpoint, complete competent legislative/policy successor channel, terminal chain, immutable evidence | Missing | Locate and exhaust a competent MOF/STA/NPC channel through cutoff. |


### Located official representations (not verified current status)

| Representation owner / host | Exact document and URL | Candidate support | Limitation |
|---|---|---|---|
| PRC President / legislative authority; STA policy-library host | **中华人民共和国印花税法（中华人民共和国主席令第八十九号）** — <https://fgk.chinatax.gov.cn/zcfgk/c100009/c5193058/content.html> | Art. 3, Art. 5(4), schedule, Art. 14, Art. 20: base `1‰`, transferor/seller, transaction amount; effective 2022-07-01; repeals former provisional regulations. | 2021-06-10 is document date, not `official_record_as_of`; located library representation has no captured post-target status/history proof. |
| MOF and STA joint issuers; STA policy-library host | **财政部 税务总局关于减半征收证券交易印花税的公告（财政部 税务总局公告2023年第39号）** — <https://fgk.chinatax.gov.cn/zcfgk/c102416/c5211343/content.html> | Effective 2023-08-28, halves securities-transaction stamp duty; with the Law, candidate `0.5‰` seller-only trade-notional. | 2023-08-27 is document date, not official record-state date; no successor/correction closure. |
| China Government reproduction | <https://www.gov.cn/zhengce/zhengceku/202308/content_6900443.htm> | Potential official duplicate representation for comparison. | No explicit correction link; do not label duplicate/correction until official evidence says so. |

### Minimal history

Only the Law and Announcement 2023 No.39 are necessary. The Law supplies economics and legal base; No.39 changes collection level. Do not acquire repealed provisional-regulation history unless a post-target candidate requires it.

### Exact endpoints and termination

- `GET` both STA-hosted record URLs above; capture raw/rendered records, every schedule/attachment, headers/redirects, receipts/digests, and source-declared status/history links. A direct HTTP 403 in this environment is an acquisition limitation, not status evidence.
- **Acquisition blocker — STA exact-search schema.** `GET https://www.chinatax.gov.cn/search5/search/s` first with the fixed No.39 fields `siteCode=bm29000002`, `searchSiteName=GSFFK`, `docType=财政部税务总局公告`, `docYear=2023`, `docNo=39`, `pageNum=0`; capture the returned raw form/JSON and record every actual `column`/`label` field/value in `request.json`. Reissue with those recorded values only. If the response supplies no such fields or documented total/page protocol, preserve this failed discovery and stop exact-act inventory qualification; do not use guessed “applicable” fields.
- Subject discovery uses preserved parameterized searches for `中华人民共和国印花税法`, `证券交易印花税`, and `减半征收证券交易印花税`; start zero-based `pageNum=0`, capture through `ceil(total/10)` and final page. This only terminates those query sets.
- `GET` gov.cn representation and normalize/compare its text against the STA-hosted representation without asserting correction.
- **Acquisition blocker — competent tax history.** From each captured STA policy record and the STA search response, follow only issuer-linked MOF/STA/NPC validity, legislative-history, amendment, repeal, or correction index URLs. Capture the index landing page and scripts; accept it only if the competent authority declares its covered corpus and date/version range. Record its exact request schema and enumerate declared first-to-terminal pagination through the frozen cutoff. If no such declared index is linked/discovered, retain the discovery source refs and stop `INSUFFICIENT`.

### Expected artifacts and stop conditions

Artifacts: Law raw/rendered/schedule; No.39 raw/rendered; STA search JSON pages; gov.cn comparison source; competent post-target index and candidate attachments; receipts/digests.

Stop as **INSUFFICIENT** if the post-target record state or competent complete channel is unavailable, if representation relationship remains undocumented, or if the execution tuple remains unsupported. Do not project `0.5‰` seller-only candidate economics into the frozen tuple.

## Cross-lineage closure checklist

Closure requires all of the following for every applicable lineage:

1. A competent, source-declared record state at/after the exact cutoff.
2. Immutable raw/rendered/attachment evidence and receipt/hash manifest for selected documents and indexes.
3. A complete, issuer-authoritative, range-terminated amendment/correction/repeal/successor inventory to that record state.
4. Deterministic dispositions and expressly supported documentary/economic relations for every candidate.
5. Complete proof of the frozen execution tuple, or an explicitly valid route-exclusion predicate (HKSCC only: conditional `applies=false`, never zero rate).
6. Separate retention and reasoning for ChinaClear transfer, HKSCC China-Connect transfer, SZSE handling, NDRC/MOF regulatory standard, SZSE regulatory collection, and stamp duty.

Until then, all candidate economics remain research observations only, and RuleBook/closure production is prohibited.
