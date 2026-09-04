# G12H competent status-register discovery v1

## Result

Target: `2026-07-30T16:00:00Z` (`2026-07-31 00:00:00+08:00`) for XSHE domestic ordinary A-share trade-notional charges.

**All five economic lineages remain INSUFFICIENT.** Official category registers, specific amendment records, exact status APIs, and prospective-successor documents were located and captured, but no common qualified `official_record_as_of` can be selected. No RuleBook value, F2 projection, F3 publication, analyzer work, or qualification is authorized.

This phase is additive to immutable Wave 1 evidence. Captures live under `evidence/g12h-register-discovery-v1/`; Wave 1 bytes, manifests, ledgers, hashes, and commits remain unchanged.

| Artifact | Frozen value |
|---|---|
| Official source packages | 28 HTTP 200 packages |
| Evidence files | 406 files; root ledger has 405 entries and excludes itself |
| Manifest | `evidence/g12h-register-discovery-v1/manifest.json`; `sha256:fe2961439a04edfda08b07366ebaf4cb192f6a9356053ed7f788de2ba6e8daf4` |
| Ledger | `evidence/g12h-register-discovery-v1/sha256sums.txt`; `sha256:a84ab8a3a7aae8eac51cc57e3bb5aedd28bf8cd4b570a1ab69f7875a8d768da5` |
| Assessment | `evidence/g12h-register-discovery-v1/analysis/status-register-assessment.json`; `sha256:57a3a3aa7c5cb75eb2d2f347a64f54a267ecc6ea4c872e9e0029ee89068fa0fc` |
| Operator manifest | `evidence/g12h-register-discovery-v1/operator/manifest.json`; `sha256:681e245e3ed77d4da0c536218e760c267ce6a31eed390a4bde4062b90b459ff6` |
| Private-header receipt | `evidence/g12h-register-discovery-v1/private-response-header-store-receipt.json`; `sha256:e0da51c3347ad2bdf01c6ddb0142e109f22f78725b419deb441c132b288012f3` |

Exact transient-cookie-bearing header/redirect/transport bytes are retained mode-restricted at `/srv/bcache-8t/ygguo/backtest/g12h-authority-private/20260820-register-discovery-response-headers`; private manifest `sha256:890c417a4916aa9ada25188e7d3503490dc28162bc53937901e0bb67080eddcd`.

Operator provenance keeps both exact executed and hardened copies. The NPC POST receipt binds exact executed harness `sha256:7de8a942b0580797bbd3c8eddac7876f874bb40c13fd6988e142e96955e5f169`; the exact executed cookie redactor is `sha256:47895c343fd59abe8d1883240e16429b2a09e2907f0091e82d3d0c5f87e92c7b`, bound to its outputs by `operator/redaction-execution-receipt.json`. Root-level copies are hardened reconstructions for static checking and are not substituted for executed-source identity.

## Register assessment

| Lineage | New competent source or mechanism | What it proves | Remaining failure |
|---|---|---|---|
| `exchange_handling` | SZSE **全部业务规则**, **规则废止公告**, **已废止规则文本**, and **深圳证券交易所业务收费管理办法** | The rule pages explicitly define a business-rule/repeal corpus. The Measures establish governance for establishing, changing, cancelling, reducing, or restoring charges. | The January 2026 fee table is published under market-services/fees and is not declared to be in those business-rule corpora. No fee-table-specific validity/version/successor register or post-target dated status was found. |
| `securities_regulatory` | Existing NDRC/MOF individual acts plus NDRC normative-file and MOF current-catalogue mechanisms identified in research | 2018 No. 917 remains direct scope/rate/effective-date evidence and expressly repeals 2016 No. 14. Broad official catalogues can corroborate individual instruments/items. | No competent post-target register declares a complete amendment/repeal/correction/successor lineage for the Shanghai/Shenzhen regulatory-fee authority and the separate SZSE collection representation. |
| `chinaclear_transfer` | ChinaClear **已废止业务规则** and **已废止业务规则文本** pages and iframes | These are real issuer-owned repealed-business-rule categories with explicit `已废止` entries. | Their declared corpus is business rules, not fee-standard tables. They cannot establish the current/history state of the Shenzhen A-share stock-transfer-fee PDF. |
| `hkscc_transfer` | Specific approved 2025 HKSCC amendments, their markups, and the 2026 USM draft/circular package | 019/2025 amendments took effect 2025-06-30; 038/2025 amendments took effect 2025-10-02. The USM package is an explicitly prospective successor, targeted for 2026-11-16 and not implemented at the cutoff. | No source declares the clean Definitions and §21 document identities/version at the cutoff, or that the Rule Update/circular channels are complete for amendments, corrections, replacements, and withdrawals. |
| `stamp_duty` | NPC National Database current-status search/detail API; STA advanced-search status vocabulary and exact No. 39 result | NPC exact-title search returns the Stamp Duty Law with `sxx=3` (`有效`), effective 2022-07-01; detail returns no `lsyg` or `flfg` chain and empty `xgwj`. STA defines explicit status values but returns blank status/repeal/revision fields for Announcement 2023 No. 39. | The NPC response has no source-declared record-state timestamp at/after the cutoff, so receipt time cannot become `official_record_as_of` under the frozen capture plan. No. 39 has no declared terminal state or complete history chain. |

## Captured official evidence

### SZSE

- Fee Management Measures: <http://docs.static.szse.cn/www/marketServices/deal/payFees/W020200228805325484325.pdf>
- All business rules: <https://www.szse.cn/lawrules/rule/allrules/bussiness/>
- Repeal announcements: <https://www.szse.cn/lawrules/rule/repeal/announcement/>
- Repealed-rule texts: <https://www.szse.cn/lawrules/rule/repeal/rules/>

The captured Measures state that SZSE publishes fee items and standards, evaluates them continuously, and has governance for new, cancelled, adjusted, reduced, exempted, or restored charges. That governance does not itself enumerate the table's revision chain.

### ChinaClear

- Repealed business-rule category: <https://www.chinaclear.cn/zdjs/yfzywgz/law_flist.shtml>
- Repealed business-rule list iframe: <https://www.chinaclear.cn/zdjs/yfzywgz/law_flist/code_1.shtml>
- Repealed-rule text category: <https://www.chinaclear.cn/zdjs/yyfzywgz/law_list.shtml>
- Repealed-rule text iframe: <https://www.chinaclear.cn/zdjs/yyfzywgz/law_list/code_2.shtml>

The pages explicitly label their corpus `业务规则 / 已废止业务规则`; the fee-standard section remains a separate navigation category. Absence of a stock-transfer-fee table from this corpus is not continuity proof.

### HKSCC

- 019/2025 circular and OP amendment: the circular states that approved amendments **“will come into effect on Monday, 30 June 2025.”**
- 022/2025 STMC markup: specific Definitions comparison effective 2025-06-30 per the official Rule Update channel.
- 038/2025 circular and markup: the circular states that approved amendments **“will come into effect on Thursday, 2 October 2025.”** This is pre-target for the July 2026 scope and has no effect on the transfer-fee predicate; it remains relevant only to exact §21 document-version reconstruction.
- 2026 USM draft: **“for indicative purposes only”**, **“have not yet been implemented”**, and the HKSCC Operational Procedures **“remain subject to change.”**
- Circular 100/2026 states the USM regime was targeted for **16 November 2026**.

These documents allow deterministic disposition of identified candidates but do not prove that the identified candidate set is complete.

### NPC Stamp Duty Law current-status API

Official base: <https://flk.npc.gov.cn/>

Captured exact search:

```http
POST /law-search/search/list
Content-Type: application/json;charset=UTF-8
```

```json
{
  "searchRange": 1,
  "searchContent": "中华人民共和国印花税法",
  "searchType": 1,
  "sxx": [3],
  "sxrq": [],
  "gbrq": [],
  "gbrqYear": [],
  "flfgCodeId": [],
  "zdjgCodeId": [],
  "orderByParam": {"order": "-1", "sort": ""},
  "pageNum": 1,
  "pageSize": 20
}
```

Response facts:

- `total = 1`
- canonical `bbbs = ff80818179f5da5e0179f890885b0481`
- `sxx = 3`
- promulgated `2021-06-10`
- effective `2022-07-01`
- issuing authority: 全国人民代表大会常务委员会

Captured detail:

```http
GET /law-search/search/flfgDetails?bbbs=ff80818179f5da5e0179f890885b0481
```

It returns the exact Law with `sxx=3`, `lsyg=null`, `flfg=null`, and `xgwj=[]`. The captured official client maps statuses as:

```text
4 = 尚未生效
3 = 有效
2 = 已修改
1 = 已废止
```

This is the strongest status evidence found. It remains partial under the frozen acceptance rule because neither search nor detail response supplies a source-declared record-state/as-of timestamp.

### STA/MOF Announcement 2023 No. 39

- STA advanced search: <https://fgk.chinatax.gov.cn/zcfgk/c100028/search.html>
- STA request builder: <https://fgk.chinatax.gov.cn/zcfgk/xhtml/js/getSearch.js>
- MOF original publication: <http://szs.mof.gov.cn/zhengcefabu/202308/t20230827_3904226.htm>

The STA UI declares the status vocabulary `全文有效`, `已修改`, `全文失效`, `全文废止`, and `尚未生效`, mapped to query field `xxgkAging`. The exact No. 39 hit identifies the document but returns:

```json
{
  "xxgk_aging": "",
  "xxgk_abolishDate": "",
  "xxgk_reviseType": ""
}
```

Blank is **UNDECLARED**, not “effective,” and the result provides no version-history array.

## Boundary decision

`official_record_as_of` and `closure_evidence_available_at` remain unset. Current-page presence, transport dates, retrieval receipts, search absence, and category absence are not promoted to legal continuity proof.

The remaining acquisition is no longer ordinary website crawling. A positive result now requires one of:

1. an issuer-authenticated archive export or status certificate with declared corpus-through date and complete lineage relations;
2. an official status/history API response that includes a source-declared record-state timestamp at/after the cutoff; or
3. a governance decision explicitly relaxing the frozen source-declared-as-of requirement for an official live current-status API. No such relaxation is authorized here.

Until then, all five lineages remain fail-closed and the discovered candidate relations are research evidence only.
