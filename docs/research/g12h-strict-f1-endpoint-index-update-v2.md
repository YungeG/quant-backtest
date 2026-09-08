# Research: strict G12H F1 endpoint-index latest-first update v2

## Summary

A bounded latest-first search of issuer-owned SZSE, NDRC, ChinaClear, HKEX/HKSCC, STA, and NPC channels found **no genuinely new qualifying status/history/index/certificate endpoint** for the July-2026 XSHE `DOMESTIC + ORDINARY_A_SHARE` target. The strongest live checks were duplicates of already captured endpoints or returned blank/undeclared exact-act status, so the required stop rule fired and all five dimensions remain strict F1 blockers with `official_record_as_of` unset.

## Scope and inherited decision rules

Reviewed repository evidence and decisions:

- `docs/research/g12h-xshe-domestic-ordinary-wave1-capture-result-v1.md`
- `docs/research/g12h-competent-status-register-discovery-v1.md`
- `docs/research/g12h-live-status-api-probes-v1.md`
- `docs/research/g12h-xshe-domestic-ordinary-successor-closure-f1-authority.md`
- `docs/research/g12h-xshe-july-2026-full-envelope-successor-closure-f1.md`
- `docs/adr/0004-official-rules-effective-until-authoritatively-superseded.md`
- `docs/adr/0006-explicit-official-live-status-may-use-receipt-time.md`
- `docs/adr/0007-current-official-selection-supports-development-projection.md`

Strict F1 requires a source-declared record cutoff or an issuer-owned live response identifying the exact act with an explicit nonblank status. Request success, current-page selection, page presence, blank status, search absence, and receipt time alone do not qualify. ADR 0007 current-document evidence is development-only and cannot set `official_record_as_of`.

## Findings

1. **Blocker — SZSE handling fee: duplicate current selector; status remains blank.** The official `GET /marketServices/deal/payFees/index.json` response still selects only `/marketServices/deal/payFees/t20251231_618209.json`, with `pubTime=1767144191000` and `docTitleStatusTime=""`. `code=0` / `message=成功` is transport/application success, not exact-document validity. This exactly duplicates `evidence/g12h-live-status-api-probes-v1/exchange_handling/szse-fee-selector-json-live/` and triggers the duplicate/blank stop. Verdict: **BLOCKED — `CURRENT_DOCUMENT_SELECTOR_CONFIRMED_STATUS_UNDECLARED`; no new evidence captured.** [SZSE selector](https://www.szse.cn/marketServices/deal/payFees/index.json)

2. **Blocker — NDRC regulatory fee: alternate query form is only a duplicate representation.** The official 2018 No.917 URL with `state=123` returns the same act text: 0.02‰ on Shanghai/Shenzhen stock turnover, effective 2018-01-01, expressly replacing 2016 No.14. It exposes no explicit current validity, modification, repeal, correction, successor, or record-as-of field. The later 2021 No.1947 result remains context rather than exact XSHE successor closure. Verdict: **BLOCKED — no post-target exact-act status/history endpoint; no new evidence captured.** [NDRC 2018 No.917](https://www.ndrc.gov.cn/xxgk/zcfb/ghxwj/201806/t20180627_960950.html?code=&state=123) · [NDRC 2021 No.1947](https://www.ndrc.gov.cn/xxgk/zcfb/tz/202201/t20220107_1311590_ext.html)

3. **Blocker — ChinaClear transfer fee: search rediscovered only the known fee-standard and repealed-business-rule channels.** Latest-first discovery returned the issuer's existing `收费标准` list, chronology, and `已废止业务规则` category. The fee list remains a mutable fee-table corpus with no declared validity/version/history state for the Shenzhen A-share stock-transfer schedule; the repealed category declares a business-rule corpus, not fee-standard tables. Direct extraction of the fee list was incomplete, so under the bounded rule the run stopped rather than broadening collection. Verdict: **BLOCKED — `FEE_TABLE_STATUS_CORPUS_NOT_DECLARED`; no new evidence captured.** [ChinaClear fee standards](http://www.chinaclear.cn/zdjs/fbzyls/service_tlist.shtml) · [ChinaClear repealed business rules](http://www.chinaclear.cn/zdjs/yfzywgz/law_flist.shtml)

4. **Blocker — HKSCC transfer: only known current Section 21 and Rule Update channels were rediscovered.** Official search returned current Operational Procedures Section 21 and the Rule Update index already assessed in register discovery. Section 21 continues to state the China-Connect-only transfer-fee predicate, but neither the clean Section 21/Definitions representation nor the Rule Update channel declares a post-target exact-version status, complete correction/successor corpus, or record-through timestamp. The known 2026 USM documents remain prospective and explicitly non-implemented for the target. Verdict: **BLOCKED — domestic `applies=false` remains a candidate, not strict closure; no new evidence captured.** [HKSCC Operational Procedures](https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Rules/HKSCC/Operational-Procedures?sc_lang=en) · [HKSCC Rule Update index](https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Rules/HKSCC/Rules/Rule-Update_HKSCC-Operational-Procedures?sc_lang=en)

5. **Blocker — STA stamp duty: exact No.39 status remains blank/unclassified.** The official No.39 policy page was rediscovered, but no explicit exact-act status appeared. Existing captured live queries already prove the exact record is returned only unfiltered with `xxgk_aging=""`, `xxgk_abolishDate=""`, and `xxgk_reviseType=""`, while all five published status filters return zero. The NPC live API's `sxx=3` applies to the Stamp Duty Law, not Announcement 2023 No.39; it cannot silently establish the half-collection act's status. Verdict: **BLOCKED — `NO39_EXPLICITLY_UNCLASSIFIED_ACROSS_PUBLISHED_STATUS_FILTERS`; no new evidence captured.** [STA No.39](https://fgk.chinatax.gov.cn/zcfgk/c102416/c5211343/content.html) · [NPC legal database](https://flk.npc.gov.cn/)

6. **Non-qualifying latest official directory — NPC's 2026 current-law list predates target end.** A newly discoverable China NPC page lists `现行有效法律目录（311件）` with a displayed date of 2026-07-08. Even if it includes the Stamp Duty Law, that date is before the target endpoint (`2026-07-31 00:00:00+08:00`) and does not identify or status Announcement No.39. It cannot supply strict F1 `official_record_as_of` and was not captured as new evidence. [NPC Legislative Affairs Commission listing](http://www.npc.gov.cn/npc/c2597/c5854/c5855/)

## Per-dimension verdict

| Dimension | Latest-first result | Strict F1 verdict | Severity |
| --- | --- | --- | --- |
| SZSE handling fee | Known selector repeated; exact document status blank | **BLOCKED** | blocker |
| NDRC regulatory fee | Known act/alternate URL repeated; no current exact-act state | **BLOCKED** | blocker |
| ChinaClear transfer | Known fee/repeal channels repeated; wrong or undeclared corpus | **BLOCKED** | blocker |
| HKSCC transfer | Known Section 21/Rule Update channels repeated; no version/corpus closure | **BLOCKED** | blocker |
| STA stamp duty | No.39 remains blank across status fields/filters; NPC law status is not No.39 status | **BLOCKED** | blocker |

Overall: **`F1_BLOCKED_NO_COMMON_OFFICIAL_RECORD_AS_OF`**. `official_record_as_of=null`; no strict closure artifact, RuleBook, registry edit, or qualification is authorized.

## Evidence disposition

- **New public official response captured:** none. The only successfully read live machine response (SZSE selector) was byte-semantically duplicative in all decision fields and retained a blank status.
- **New headers/receipt/hash:** none. Creating a second evidence package for a duplicate/blank response would violate the bounded stop rule and add no authority.
- **Existing evidence changed:** none.
- **Registry/development qualification changes:** none, as required.

## Sources

- Kept: [SZSE fee selector](https://www.szse.cn/marketServices/deal/payFees/index.json) — direct official machine endpoint; confirmed duplicate selection and blank status.
- Kept: [NDRC 2018 No.917](https://www.ndrc.gov.cn/xxgk/zcfb/ghxwj/201806/t20180627_960950.html?code=&state=123) — direct official exact act; alternate URL did not add status/history semantics.
- Kept: [ChinaClear fee standards](http://www.chinaclear.cn/zdjs/fbzyls/service_tlist.shtml) — direct issuer fee-table channel; still lacks a declared status/history corpus.
- Kept: [HKSCC Rule Update index](https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Rules/HKSCC/Rules/Rule-Update_HKSCC-Operational-Procedures?sc_lang=en) — direct issuer update channel; no declared complete exact-version closure.
- Kept: [STA No.39](https://fgk.chinatax.gov.cn/zcfgk/c102416/c5211343/content.html) — exact official act; no explicit status discovered.
- Dropped: NPC `现行有效法律目录（311件）` — official but dated 2026-07-08, before target end, and does not identify No.39.
- Dropped: provincial STA copies and explanatory pages — issuer-owned government pages but not the competent exact No.39 status/history endpoint requested.
- Dropped: search snippets and all non-issuer commentary — discovery only, never authority.

## Gaps

No issuer-authenticated export, status certificate, post-target register-through declaration, exact-act nonblank live status, or complete correction/successor map was found for the five required lineages. HKEX direct fetch was also blocked by the environment's fake-IP SSRF guard, and ChinaClear/STA readable extraction was incomplete; official-domain search still showed only already assessed channels. A future bounded pass should run only after an issuer publishes a genuinely new endpoint or certificate, not repeat these blank/current selectors.

## Commit and validation disposition

- Repository commit: **not produced in this research child run**; available tools did not include Git execution, and the authoritative runtime output is outside the repository worktree.
- Commit hash: **none**.
- Report path: `/tmp/backtest-g12h-f1-update-v2/research.md`.
- Validation: report written; source citations are issuer-owned; no evidence, registry, qualification, or development files were edited.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Concrete blocker findings and severities are recorded for all five dimensions in /tmp/backtest-g12h-f1-update-v2/research.md; no qualifying new endpoint was found."
    }
  ],
  "changedFiles": [
    "/tmp/backtest-g12h-f1-update-v2/research.md"
  ],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "functions.read existing Wave1/register/live-status reports and ADRs 0004/0006/0007",
      "result": "passed",
      "summary": "Reviewed the required repository evidence and strict decision rules."
    },
    {
      "command": "functions.web_search issuer-owned SZSE/NDRC/ChinaClear/HKEX-HKSCC/STA/NPC endpoints, latest-first",
      "result": "passed",
      "summary": "Search returned duplicates, pre-target material, or endpoints without qualifying exact-act status/history closure."
    },
    {
      "command": "functions.fetch_content official SZSE selector, NDRC act, ChinaClear fee list, HKSCC update index, and STA No.39",
      "result": "passed",
      "summary": "SZSE and NDRC were readable; ChinaClear/STA extraction was incomplete and HKEX was SSRF-blocked; no genuinely new qualifying response resulted."
    },
    {
      "command": "functions.write /tmp/backtest-g12h-f1-update-v2/research.md",
      "result": "passed",
      "summary": "Wrote the bounded research brief and structured acceptance report."
    },
    {
      "command": "git status / validation / commit",
      "result": "not-run",
      "summary": "Git/shell execution is unavailable to this research child; no repository commit or hash was produced."
    }
  ],
  "validationOutput": [
    "All five dimensions: BLOCKED (severity: blocker).",
    "Overall: F1_BLOCKED_NO_COMMON_OFFICIAL_RECORD_AS_OF.",
    "No new evidence package, receipt, headers, or hash created because the live result was duplicate/blank.",
    "No registry or development-qualification edits were made."
  ],
  "residualRisks": [
    "Repository git status and commit could not be validated or produced without a Git execution tool.",
    "HKEX direct fetch was blocked by the environment SSRF guard; ChinaClear and STA readable extraction was incomplete.",
    "Future issuer publications may add post-target status/history evidence not yet indexed."
  ],
  "noStagedFiles": true,
  "diffSummary": "One external runtime research report; no repository evidence, registry, qualification, or development changes.",
  "reviewFindings": [
    "blocker: SZSE handling fee - current selector repeats known document and returns blank status.",
    "blocker: NDRC regulatory fee - no post-target exact-act status/history endpoint.",
    "blocker: ChinaClear transfer - fee-table status/history corpus remains undeclared.",
    "blocker: HKSCC transfer - no post-target exact-version or complete successor/correction closure.",
    "blocker: STA stamp duty - Announcement 2023 No.39 remains explicitly unclassified/blank."
  ],
  "manualNotes": "The parent session must perform any desired repository copy, git validation, and commit; this child produced only the authoritative runtime report."
}
```
