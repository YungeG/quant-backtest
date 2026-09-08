# F1 research — XSHE domestic ordinary-A-share trade-notional fee/tax successor closure

## Result

**No lineage is closed. F1 remains blocked; no closure artifact or RuleBook is supportable.** ADR 0004 requires a terminal documentary representation, a complete economic-successor chain, a post-target official endpoint, and a complete competent-authority candidate index. ADR 0005 narrows this run to execution-enforced `DOMESTIC + ORDINARY_A_SHARE`, retaining ChinaClear and HKSCC as distinct lineages. The primary materials below establish useful predecessor economics, but not those closure controls.

Target preserved: `Asia/Shanghai [2026-07-06 00:00:00+08:00, 2026-07-31 00:00:00+08:00)` (`UTC [2026-07-05T16:00:00Z, 2026-07-30T16:00:00Z)`). No defensible `official_record_as_of` is available from the reviewed material: no captured issuer index/table proves complete pagination/range termination and a record state at or after `2026-07-31`. Do not substitute retrieval time, the legacy composition time, or a page's old publication date.

Exact F1 scope remains fail-closed as one tuple:

```text
venue_id: XSHE
instrument_type: InstrumentType.EQUITY
quote_currency_id: CNY
settlement_currency_id: CNY
trade_mechanism: AUCTION
board_scope: all_profile_admitted_boards
execution_access_route: DOMESTIC
fee_product_class: ORDINARY_A_SHARE
basis: trade_notional
```

The reviewed sources do not close any omitted or broader scope; any ambiguity in these fields remains a blocker.

## Method and limits

Only issuer-controlled materials were treated as authority: SZSE, NDRC/MOF, ChinaClear, HKEX/HKSCC, and MOF/STA/China Government. Search results were discovery aids only; no secondary source is authority. A current page/status is an endpoint **candidate**, not proof that no successor exists. Documentary correction (a replacement representation of the same act) and economic succession (a later complete applicable state) are separately unresolved unless an official correction/repeal/amendment channel has been completely captured.

The authoritative `official_record_as_of` and `closure_evidence_available_at` must be selected only after acquisition receipts are made. They must satisfy `2026-07-30T16:00:00Z <= official_record_as_of <= closure_evidence_available_at`.

## Lineage findings

### 1. `exchange_handling` — **blocked** (`ENDPOINT_EVIDENCE_MISSING`, `SUCCESSOR_INDEX_INCOMPLETE`)

* **Predecessor/economic state.** SZSE's fee table labels the charge object `A股` and says: `按成交额双边收取0.0341‰`; its note says that from `2023年8月28日`, A/B-share handling changed from `0.0487‰` bilateral to `0.0341‰` bilateral. Thus the candidate domestic ordinary-A-share state is 0.0341 per mille (0.00341%), trade consideration/notional, buyer and seller, effective 2023-08-28. [SZSE fee table](https://www.szse.cn/marketServices/deal/payFees/index.html)
* **Scope.** The same table separates A shares from B shares, funds, preferred stock (80% during the pilot), etc. It supports only the requested ordinary A-share cash-auction candidate; its block-trade discount must not be used for `AUCTION`. The 2026 trading rules state only that participants pay handling fees under applicable rules, rather than stating a successor or validity endpoint. [SZSE Trading Rules (2026), arts. 9.2–9.3](https://docs.static.szse.cn/www/lawrules/rule/trade/current/W020260424690713155663.pdf)
* **Endpoint/index status.** The table is titled `深交所收费及代收税费标准（2026年1月）`, therefore it predates target end. The 2023 reduction notice, the fee-table revision/history endpoint, SZSE notices/corrections/repeals, and a complete paginated inventory through an after-target record date were not captured. The table has no stated `corrects_revision_id`, no successor/repeal index, and no reliable as-of receipt in this run.
* **Candidate dispositions.** 2023 reduction: `target candidate, unresolved successor closure`; 2026-01 table: `pre-target endpoint candidate only`, not economic succession. No documentary correction is established; no economic successor is established.

### 2. `securities_regulatory` — **blocked** (`AUTHORITY_SCOPE_GAP`, `ENDPOINT_EVIDENCE_MISSING`, `SUCCESSOR_INDEX_INCOMPLETE`)

* **Controlling-rate state.** NDRC/MOF 发改价格规〔2018〕917号 says: `对上海、深圳证券交易所收取证券业务监管费，按股票交易额的0.02‰收取`; section IV makes the business-rate standard effective `2018年1月1日` and simultaneously abolishes 发改价格〔2016〕14号. This proves the predecessor/replacement relation and candidate 0.02 per mille (0.002%) stock-turnover basis, but the stated payor is the exchanges, not investors. [NDRC/MOF 917](https://www.ndrc.gov.cn/xxgk/zcfb/ghxwj/201806/t20180627_960950.html?code=)
* **XSHE bilateral collection applicability.** The SZSE table separately lists `证券交易监管费`, `A股`, `按成交额双边收取0.02‰`, `代中国证监会收取`. This is required complementary execution evidence for bilateral domestic investor collection; 917 alone cannot supply it. [SZSE fee table](https://www.szse.cn/marketServices/deal/payFees/index.html)
* **Later official context, not closure.** NDRC/MOF 发改价格〔2021〕1947号 says Beijing's business fee uses the same Shanghai/Shenzhen standard and that NDRC/MOF will evaluate and adjust standards as circumstances change. It neither republishes a full Shenzhen economic state nor terminates the 917 successor channel. [NDRC/MOF 1947](https://www.ndrc.gov.cn/xxgk/zcfb/tz/202201/t20220107_1311590_ext.html)
* **Endpoint/index status and dispositions.** 917 is `target candidate; predecessor 2016 replaced`; the SZSE table is `pre-target collection endpoint candidate`; 1947 is `context/no proven economic successor for XSHE`. Missing are a controlling-authority validity/repeal/adjustment index through an after-target record date **and** an XSHE table-version/correction index proving the bilateral-pass-through representation. Consequently neither documentary terminal selection nor an economic chain is possible.

### 3. `chinaclear_transfer` — **blocked** (`ENDPOINT_EVIDENCE_MISSING`, `SUCCESSOR_INDEX_INCOMPLETE`)

* **Predecessor/economic state.** ChinaClear's 28-Apr-2022 notice is the competent transition act. It was published 2022-04-28 and states the stock-trade transfer fee is reduced by 50% from 2022-04-29. The contemporaneous ChinaClear corporate chronology independently identifies the act/date. The notice must be captured as bytes because the readable extractor was incomplete in this run. This report does **not** freeze an exact post-reduction rate, side applicability, or complete scope until those fields are extracted from captured official bytes. [ChinaClear 2022 notice](https://www.chinaclear.cn/zdjs/gszb/202204/837e3c5031104aa099d6597ba381342a.shtml) · [ChinaClear chronology](http://www.chinaclear.cn/zdjs/dsj/about_dsj.shtml)
* **Scope separation.** It is a ChinaClear charge. ADR 0005 prohibits merging it with the separate HKSCC China Connect charge. The relevant ChinaClear service channel is its official fee-standard list, but a saved complete list response/cursor termination was not produced. [ChinaClear fee-standard channel](http://www.chinaclear.cn/zdjs/fbzyls/service_tlist.shtml)
* **Endpoint/index status and dispositions.** 2022 reduction: `target candidate; predecessor economic state reduced 50%`; fee-standard list: `official index-channel candidate, not captured/terminated`; a local previously identified Shenzhen PDF dated December 2025 is before target end, hence only `pre-target corroborating endpoint candidate`. Missing: raw notice/PDF/list bytes, the exact old/new rates and sides extracted from the act, notice/table correction links, all page(s)/attachments in the list through a record date after target end, and an authoritative successor/repeal disposition. No documentary correction or economic successor is proved.

### 4. `hkscc_transfer` — **blocked, though the domestic economic conclusion is strongly scope-supported** (`ENDPOINT_EVIDENCE_MISSING`, `SUCCESSOR_INDEX_INCOMPLETE`)

* **Explicit China-Connect-only predicate.** HKSCC Operational Procedures §21.1A calls this a transfer fee `payable by each China Connect Clearing Participant for each China Connect Securities Trade cleared and settled through HKSCC pursuant to Chapter 41`; it sets `0.002% of gross value` and says it is in addition to the SEHK Rules 14A11/14B11 transfer fee. [HKSCC Operational Procedures, §21](https://www.hkex.com.hk/-/media/HKEX-Market/Services/Rules-and-Forms-and-Fees/Rules/HKSCC/Operational-Procedures/SEC21.pdf)
* **Explicit definition establishing non-applicability to the requested domestic route.** The HKSCC definition says a `China Connect Securities Trade` is a trade in China Connect Securities `executed on a China Connect Market through an SEHK Subsidiary under a Trading Link`. An XSHE `DOMESTIC` auction is not such a trade under the execution-bound route contract. This is the required positive scope evidence for the candidate `applies=false` domestic HKSCC state; it is not an inference from a zero amount or from a missing row. [HKSCC definition in Shenzhen-Connect operational-procedure update](https://www.hkex.com.hk/-/media/HKEX-Market/Services/Rules-and-Forms-and-Fees/Rules/HKSCC/Rule-Update_Operational-Procedures/106-16-CCASSOP-Shenzhen-HK-Stock-Connect_e.pdf)
* **Corroborating official fee page.** HKEX labels the schedule `Clearing and Settlement (Stock Connect Northbound)` and lists `Transfer Fee | China Connect securities trade | 0.002% of gross value`, in addition to the ChinaClear fee. This confirms that it is not the domestic ChinaClear line. [HKEX Northbound clearing/settlement fees](https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Fees/Securities-(Stock-Connect)/Clearing-and-Settlement?sc_lang=en)
* **Endpoint/index status and dispositions.** §21/current HKEX page: `domestic-not-applicable candidate, with explicit exclusive predicate`; 2022 HKSCC circular changing the ChinaClear Northbound fee from 0.002% to 0.001% is `outside-scope corroboration`, not this HKSCC fee and not a domestic act. [HKSCC circular 017/2022](https://www.hkex.com.hk/-/media/HKEX-Market/Services/Circulars-and-Notices/Participant-and-Members-Circulars/HKSCC/2022/ce_HKSCC_SET_017_2022_.pdf) Missing: version/record date of §21 and definition, the HKSCC rules/Operational-Procedures amendment index and complete circular pages through a post-target cutoff, PDFs/HTML bytes and receipts, and a disposition of every amendment. Therefore the documentary/current representation and economic non-applicability state cannot be marked closed even though the direct route predicate is adequate in principle.

### 5. `stamp_duty` — **blocked** (`ENDPOINT_EVIDENCE_MISSING`, `SUCCESSOR_INDEX_INCOMPLETE`)

* **Statutory predecessor/base state.** The Stamp Tax Law defines securities trading as transfer of shares/depository receipts traded on a legally established exchange or other State-Council-approved national venue. Article 3 makes only the transferor liable; article 5(4) makes transaction amount the tax basis; the schedule rate is 1 per mille. Article 14 makes the securities registration and clearing institution the withholding agent; article 20 commenced the law on 2022-07-01 and repealed the former regulation. [STA policy library, Stamp Tax Law](https://fgk.chinatax.gov.cn/zcfgk/c100009/c5193058/content.html)
* **Half-collection act.** MOF/STA Announcement 2023 No.39 says: `自2023年8月28日起，证券交易印花税实施减半征收`. Against the statutory 1‰ rate, the candidate domestic ordinary-A-share result is 0.5‰ (0.05%) of trade notional, seller/transferor only, effective 2023-08-28. The STA policy record identifies issuer, act date 2023-08-27 and effective status; the State Council publication is a second official representation. [STA policy library, Announcement 39](https://fgk.chinatax.gov.cn/zcfgk/c102416/c5211343/content.html) · [China Government publication](https://www.gov.cn/zhengce/zhengceku/202308/content_6900443.htm)
* **Endpoint/index status and dispositions.** Stamp Tax Law: `base predecessor, target candidate`; Announcement 39: `target-affecting economic successor/half-collection candidate`; current STA status: `endpoint candidate only`, not a dated complete historical register. Missing: raw law schedule attachment/HTML and Announcement 39 representations, confirmation of whether any representation corrects another, the MOF/STA legislative and policy-library validity/repeal/correction indexes with complete pagination through an after-target record date, and candidate-by-candidate dispositions. “有效/全文有效” on a current record is not equivalent to a terminal index or proof of no short-lived/retroactive correction.

## Cross-lineage closure matrix

| Lineage | Candidate target economics | Official endpoint at/after target end | Complete successor/correction channel through defensible cutoff | Verdict |
| --- | --- | --- | --- | --- |
| exchange_handling | 0.0341‰, notional, bilateral, A share, from 2023-08-28 | No — displayed table is Jan-2026 | No | **blocked** |
| securities_regulatory | 0.02‰, stock turnover; XSHE separately displays bilateral investor collection | No | No, and controlling-rate/collection channels remain split | **blocked** |
| chinaclear_transfer | 50% reduction effective 2022-04-29; exact rate/sides/scope not frozen without captured official bytes | No proven after-target table/register | No | **blocked** |
| hkscc_transfer | `applies=false` for DOMESTIC; HKSCC 0.002% is China-Connect-only | No dated post-target representation | No | **blocked** |
| stamp_duty | 1‰ statutory seller-only × half collection = 0.5‰ from 2023-08-28 | No dated complete post-target register | No | **blocked** |

## Acquisition-ready manifest

| URL | Issuer / official act | Representation | Effective / record date | Required capture notes |
| --- | --- | --- | --- | --- |
| <https://www.szse.cn/disclosure/notice/general/t20230818_602805.html> | SZSE, 2023 handling-fee reduction notice | HTML plus attachments/redirect chain | effective 2023-08-28 | Capture raw and rendered representations; find notice/correction/repeal and fee-table revision indexes; paginate to terminal response after target. |
| <https://www.szse.cn/marketServices/deal/payFees/index.html> | SZSE, fee and collected-tax table | mutable HTML/rendered DOM | table label Jan-2026 | Preserve HTML/DOM/headers; record page label; acquire later dated table or historical version at/after 2026-07-31; capture all table versions/index pagination. |
| <https://www.ndrc.gov.cn/xxgk/zcfb/ghxwj/201806/t20180627_960950.html?code=> | NDRC/MOF 发改价格规〔2018〕917号 | HTML | effective 2018-01-01 | Capture exact text and metadata plus official validity/repeal/adjustment index; separately retain XSHE bilateral collection proof. |
| <https://www.ndrc.gov.cn/xxgk/zcfb/tz/202201/t20220107_1311590_ext.html> | NDRC/MOF 发改价格〔2021〕1947号 | HTML | dated 2021-12-30 | Treat as candidate context; index all later fee-adjustment acts, not as conclusive 917 successor. |
| <https://www.chinaclear.cn/zdjs/gszb/202204/837e3c5031104aa099d6597ba381342a.shtml> | ChinaClear, reduction of stock transfer fee | HTML/attachment | effective 2022-04-29 | Capture exact notice and attachments; extract old/new amount/sides/scope; get ChinaClear national/Shenzhen successor and correction list with terminal pagination. |
| <http://www.chinaclear.cn/zdjs/fbzyls/service_tlist.shtml> | ChinaClear fee-standard channel | list HTML and every child PDF | capture record date must be >= target end | Preserve request params, pages/cursors/count/terminal empty response and every linked PDF hash. |
| <https://www.hkex.com.hk/-/media/HKEX-Market/Services/Rules-and-Forms-and-Fees/Rules/HKSCC/Operational-Procedures/SEC21.pdf> | HKSCC OP §21 | PDF | current representation date not shown | Capture PDF bytes/page text and rule-version metadata; index Operational Procedure updates and HKSCC circulars through post-target cutoff. |
| <https://www.hkex.com.hk/-/media/HKEX-Market/Services/Rules-and-Forms-and-Fees/Rules/HKSCC/Rule-Update_Operational-Procedures/106-16-CCASSOP-Shenzhen-HK-Stock-Connect_e.pdf> | HKSCC definition / Shenzhen Connect update | PDF | effective date to extract | Preserve definition proving China-Connect-only predicate; obtain current definitions/version and amendment chain. |
| <https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Fees/Securities-(Stock-Connect)/Clearing-and-Settlement?sc_lang=en> | HKEX Northbound fee table | mutable HTML/rendered DOM | current page; no reliable record date | Capture only as Stock-Connect scope corroboration; it cannot replace a domestic endpoint or the rules-amendment index. |
| <https://fgk.chinatax.gov.cn/zcfgk/c100009/c5193058/content.html> | NPC Stamp Tax Law via STA policy library | HTML + schedule attachment | effective 2022-07-01 | Capture law, schedule attachment and policy metadata; acquire official legislative/current-validity and amendment/repeal index. |
| <https://fgk.chinatax.gov.cn/zcfgk/c102416/c5211343/content.html> | MOF/STA Announcement 2023 No.39 | HTML | act 2023-08-27; effective 2023-08-28 | Capture raw text, status metadata and correction/repeal index; also capture official gov.cn representation to resolve documentary relationship, not as automatic economic succession. |
| <https://www.gov.cn/zhengce/zhengceku/202308/content_6900443.htm> | China Government, Announcement 39 representation | HTML | published 2023-08-28 | Hash separately; compare exact text/metadata with STA; identify whether this is a documentary duplicate/correction only. |

## Recommended capture process (no secrets)

1. Freeze a UTC `closure_evidence_available_at` only after all downloads and receipts exist; choose `official_record_as_of >= 2026-07-30T16:00:00Z` from a dated issuer endpoint/index, not from filesystem time.
2. For each URL and every discovered index page/attachment, retain raw bytes, headers, final URL and redirect chain, content type/encoding, retrieval UTC, and SHA-256. Example:

```sh
u='https://www.szse.cn/marketServices/deal/payFees/index.html'
out='evidence/szse-fees-raw.html'
curl --fail --location --show-error --silent --dump-header "${out}.headers" --output "$out" "$u"
sha256sum "$out" "${out}.headers" > "${out}.sha256"
```

1. Capture rendered DOM separately where the official page is JS-driven, and hash raw HTML, DOM and extracted text separately. For PDFs, save original bytes first, then create a derivative text extraction with its own hash; never use extracted text as the original representation.
2. For each issuer channel, archive every page/attachment and the pagination/cursor inputs, reported total/count, and terminal response. Build an ordered candidate inventory with issuer act ID, representation ID, record/publish/effective date, `corrects_revision_id`, economic predecessor, and disposition. Compare duplicate official representations before asserting a correction.
3. Reconstruct the five independent chains only after the index proves its range through the chosen `official_record_as_of`. Mark an act `documentary correction` only on an official representation link; mark `economic successor` only if it changes/replaces the complete scoped state. Any unlinked candidate, gap, overlap, ambiguous scope/date, repeal-without-replacement, or missing endpoint remains fail-closed.

## Residual risks / nonclaims

* No source bytes, headers, redirects, receipts, rendered-DOM captures, or pagination termination were persisted by this research report; this is not an F1 closure artifact.
* No claim of provider/archive completeness, broker commission, rounding, rebates, Northbound/ETF/preferred economics, non-notional HKSCC costs, live use, decision grade, or deployment.
* The HKSCC conclusion is **not** “zero fee”: it is a distinct, explicit `DOMESTIC` not-applicable candidate based on the China-Connect-only legal predicate. It still needs the same version/index closure as the other lineages.
* Do not infer continuity from the absence of a search hit, a current table, an equal-rate later page, or `全文有效` status.

