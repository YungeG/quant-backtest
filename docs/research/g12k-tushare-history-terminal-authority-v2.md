# Research: G12K Tushare historical listing/membership/corporate-action terminal authority (v2)

## Summary

**Verdict: BLOCKER REMAINS — critical.** Tushare supplies useful current state, event/date histories, and a partial daily historical stock list, but no examined first-party artifact establishes a July-2026 historical-as-of listing universe with correction/supersession lineage, terminal completeness, and immutable vendor version/checksum. The strongest negative authority is Tushare’s own service agreement, which expressly declines guarantees of accuracy, completeness, and timeliness.

## Findings

1. **Critical — Backtest requires evidence that the Tushare interfaces do not publish.** Backtest `MarketEvent` requires `revision_id`, optional `supersedes_revision_id`, `source_hash`, and causal availability time; manifests require bounded coverage, event counts, stream hashes, and a manifest content hash. Its `RevisionClosureDeclaration` additionally requires a causal visibility limit and a terminal event hash for every logical lineage, while `AvailabilityClosureDeclaration` requires gap-free reasoned coverage. These are concrete terminal-authority requirements, not merely local storage preferences. Paths: `packages/market-data-contracts/src/crypto_quant_market_data/bundles.py` (`MarketEvent`, `MarketStreamManifest`, `MarketBundleManifest`) and `packages/market-bundle-builder/src/crypto_quant_bundle_builder/coverage_declarations.py` (`AvailabilityClosureDeclaration`, `RevisionClosureDeclaration`).

2. **Critical — `stock_basic` is current-selected state, not historical-as-of state.** The official page describes basic information and demonstrates “current all normally listed stocks.” It exposes current `list_status` plus `list_date`/`delist_date`, but no query-as-of parameter, announcement/availability time, revision identifier, supersedes pointer, completeness marker, dataset version, or checksum. Dates can reconstruct a simplified listed interval only if one assumes present values are final and exhaustive—an assumption Tushare does not warrant. [Official stock_basic](https://tushare.pro/document/2?doc_id=25)

3. **High — `bak_basic` is the closest historical membership artifact, but it closes only a partial analytical gap.** The issuer calls it a “backup basic list” and “historical daily stock list,” queryable by `trade_date`, with data only from 2016. It can evidence which rows Tushare currently returns for a historical trading date, but it has no explicit listing/status field, no documented semantics for absent rows, no delisting/suspension reason, no availability timestamp, and no correction or terminal lineage. It therefore supports a development-only daily-universe approximation from 2016, not terminal membership authority. [Official bak_basic](https://tushare.pro/document/2?doc_id=262) [Official markdown representation](https://tushare.pro/wctapi/documents/262.md)

4. **High — historical status auxiliaries are useful but explicitly incomplete or semantically narrow.** `namechange` provides named intervals and announcement dates, but no stable revision/action ID or supersession chain. `suspend_d` supplies daily suspension/resumption observations and says updates are irregular. `stock_st` supplies daily historical ST membership but explicitly says history starts at 2000-01-01 and earlier history cannot be completed. `bse_mapping` covers only BSE old/new code mapping. None proves the complete exchange listing universe. [Official namechange](https://tushare.pro/document/2?doc_id=100) [Official suspend_d](https://tushare.pro/document/2?doc_id=214) [Official stock_st](https://tushare.pro/document/2?doc_id=397) [Official bse_mapping](https://tushare.pro/document/2?doc_id=375)

5. **High — `new_share` is issuance/listing metadata, not lifecycle authority.** It exposes IPO and issue/listing dates and can corroborate entry events, including rows whose issue date is not yet populated, but it has no delisting, status history, correction lineage, terminal marker, or immutable snapshot identity. [Official new_share](https://tushare.pro/document/2?doc_id=123)

6. **Critical — corporate-action endpoints do not provide revision closure.** `dividend` exposes proposal/decision announcement dates, implementation progress, record/ex/pay dates, cash/stock rates, and base shares. Those fields are valuable event content, but there is no documented unique corporate-action ID, revision ID, supersedes relationship, cancellation/replacement lineage, terminal-completeness declaration, or dataset version/checksum. `adj_factor` is explicitly produced by Tushare and offers all historical factors, but only `(ts_code, trade_date, adj_factor)`; it is a current computed series updated daily, not action lineage or proof that no later correction exists. [Official dividend](https://tushare.pro/document/2?doc_id=103) [Official adj_factor](https://tushare.pro/document/2?doc_id=28)

7. **Critical — Tushare documents correction history only selectively, not for the examined endpoints.** The official FAQ explains that duplicated financial-statement rows may represent corrections and that `update_flag=1` identifies corrected financial data. None of `stock_basic`, `bak_basic`, `namechange`, `suspend_d`, `new_share`, `adj_factor`, or `dividend` documents an equivalent correction flag or revision lineage. This is direct evidence that Tushare knows how to expose revision state where designed, but does not claim it for the blocker endpoints. [Official FAQ](https://tushare.pro/document/1?doc_id=122)

8. **Critical — first-party terms negate terminal-completeness authority.** Tushare’s data-service agreement says users bear risks from errors in correctness, completeness, or timeliness; it states Tushare cannot guarantee accuracy, correctness, adequacy, completeness, or timeliness, and may change, remove, interrupt, or terminate services. That is incompatible with treating a live API response as issuer-certified terminal closure without a separate immutable/versioned artifact. [Official Tushare data-service agreement](https://tushare.pro/document/1?doc_id=405)

9. **Medium — no first-party immutable download/version/checksum was found in the bounded latest-first pass.** The official `wctapi/documents/{doc_id}.md` pages are useful first-party machine-readable documentation representations, but the URLs carry only mutable document IDs, not content versions or checksums. Searches of Tushare’s official domain found no stock-list/corporate-action archive with a vendor-declared SHA-256/MD5, immutable release version, correction ledger, or terminal receipt. SDK package versions concern client code, not dataset identity.

10. **Medium — a public unauthenticated official API probe proves reachability only.** `GET https://api.tushare.pro` returned the small first-party JSON response `{"request_id":"","code":40101,"data":null,"msg":"不是合格的json格式，EOF","detail":""}`. It provides no response data version, dataset cutoff, content checksum, or terminal receipt. No token was used or exposed. [Official API endpoint](https://api.tushare.pro)

11. **Critical — July-2026 cannot be certified.** The live homepage identifies the service as © 2026 and current official pages contain 2026-era material, but none of the examined artifacts binds listing/membership/corporate-action content to a July-2026 cutoff or declares that all corrections visible by that cutoff are included. A locally captured response hash would prove only bytes received at acquisition time; under Backtest’s own model it cannot manufacture missing vendor revision closure or terminal completeness. Backtest’s snapshot layer correctly distinguishes these concepts: `SourceSnapshotMember.declared_sha256` records a vendor-declared hash when one exists, while local `content_hash`, `snapshot_id`, and provenance hashes only freeze acquired bytes. Path: `packages/market-bundle-builder/src/crypto_quant_bundle_builder/source_snapshots.py` (`RawSourceMember`, `SourceSnapshotMember`, `freeze_source_snapshot`).

## Endpoint disposition

| Endpoint/artifact | Useful evidence | Historical-as-of | Revision/supersession | Terminal completeness | Immutable vendor version/checksum | Disposition |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| `stock_basic` | current status, list/delist dates | No | No | No | No | insufficient |
| `bak_basic` | daily returned stock rows from 2016 | Partial | No | No | No | development-only supplement |
| `namechange` | dated name intervals, announcement date | Partial | No | No | No | auxiliary only |
| `suspend_d` | dated suspend/resume observations | Partial | No | No | No | auxiliary only |
| `stock_st` | daily ST membership; admitted early gap | Partial | No | Explicitly no | No | auxiliary/incomplete |
| `new_share` | IPO and issue/listing dates | Partial entry events | No | No | No | auxiliary only |
| `dividend` | proposal/implementation and entitlement dates/rates | Event-time partial | No | No | No | insufficient for action closure |
| `adj_factor` | Tushare-produced historical factor series | Current-selected history | No | No | No | derived corroboration only |
| `bse_mapping` | BSE code replacements | Narrow partial | No | No | No | narrow auxiliary |
| `wctapi` markdown docs | machine-readable field contract | N/A | No | No | No | documentation only |

## Closure decision

- **Do not close G12K terminal authority.** Severity: **critical blocker**.
- Tushare can remain evidence for development-only/current-selected or explicitly bounded historical approximations if the consuming declaration stays `decision_grade_eligible=False` and `deployment_authorized=False`, matching Backtest’s current coverage-declaration guards.
- Closure requires a first-party Tushare artifact or contractual response that supplies, for the required July-2026 scope: (a) historical-as-of listing/membership state with documented absence semantics; (b) correction/supersession lineage for listing and corporate actions; (c) terminal completeness at a causal visibility cutoff; and (d) immutable vendor version/checksum or signed receipt. No examined source supplies that combination.

## Sources

- Kept: [股票基础信息 / stock_basic](https://tushare.pro/document/2?doc_id=25) — authoritative current listing/status schema.
- Kept: [股票历史列表 / bak_basic](https://tushare.pro/document/2?doc_id=262) — strongest historical daily-list candidate and explicit 2016 floor.
- Kept: [股票曾用名 / namechange](https://tushare.pro/document/2?doc_id=100) — dated identity/name history.
- Kept: [每日停复牌信息 / suspend_d](https://tushare.pro/document/2?doc_id=214) — dated availability/status auxiliary.
- Kept: [IPO新股列表 / new_share](https://tushare.pro/document/2?doc_id=123) — entry-event auxiliary.
- Kept: [复权因子 / adj_factor](https://tushare.pro/document/2?doc_id=28) — Tushare-produced derived corporate-action series.
- Kept: [分红送股 / dividend](https://tushare.pro/document/2?doc_id=103) — primary corporate-action schema.
- Kept: [ST股票列表 / stock_st](https://tushare.pro/document/2?doc_id=397) — historical status list with explicit incompleteness.
- Kept: [北交所新旧代码对照 / bse_mapping](https://tushare.pro/document/2?doc_id=375) — narrow code-change history.
- Kept: [常见问题](https://tushare.pro/document/1?doc_id=122) — official evidence of selective correction flagging.
- Kept: [Tushare数据服务协议](https://tushare.pro/document/1?doc_id=405) — decisive first-party non-guarantee of completeness/timeliness.
- Kept: `packages/market-data-contracts/src/crypto_quant_market_data/bundles.py` — Backtest immutable manifest and revision-bearing event evidence.
- Kept: `packages/market-bundle-builder/src/crypto_quant_bundle_builder/coverage_declarations.py` — Backtest availability and revision terminal-closure requirements.
- Kept: `packages/market-bundle-builder/src/crypto_quant_bundle_builder/source_snapshots.py` — distinction between local capture hashes and vendor-declared checksums.
- Dropped: search-engine snippets and all secondary commentary — excluded by the first-party-only constraint.
- Dropped: unrelated market/fund/index APIs — excluded because they do not answer A-share listing/membership/corporate-action closure.
- Dropped: Tushare SDK release version — client software version does not version the returned datasets.

## Gaps

- Authenticated API rows and HTTP headers were not captured because no Tushare token was available to this research run; the public unauthenticated endpoint response was captured instead.
- The available toolset could not execute `git status`, tests, hashing, or commits. The parent session should persist this brief to the requested repository documentation path if desired, run markdown/link validation, verify a clean index, and commit report/new evidence only.
- Absence of a checksum/version artifact is bounded to the official documentation, public API surface, official markdown representations, service terms, and focused latest-first official-domain searches examined here; a private enterprise delivery contract could change the verdict if it supplies the missing authority explicitly.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Concrete critical/high/medium findings identify Backtest paths packages/market-data-contracts/src/crypto_quant_market_data/bundles.py, packages/market-bundle-builder/src/crypto_quant_bundle_builder/coverage_declarations.py, and packages/market-bundle-builder/src/crypto_quant_bundle_builder/source_snapshots.py, plus first-party Tushare endpoint evidence."
    }
  ],
  "changedFiles": [
    "/tmp/backtest-g12k-authority-v2/research.md"
  ],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "Focused first-party web searches over tushare.pro for stock_basic, bak_basic, namechange, suspend_d, stock_st, new_share, adj_factor, dividend, revision, version and checksum artifacts",
      "result": "passed",
      "summary": "Located and reviewed official endpoint documentation, FAQ, terms, and official markdown representations; no terminal/versioned authority found."
    },
    {
      "command": "Fetch official Tushare documentation and public GET https://api.tushare.pro",
      "result": "passed",
      "summary": "Captured official schemas and unauthenticated JSON error response without credentials."
    },
    {
      "command": "Read Backtest evidence contracts in bundles.py, coverage_declarations.py, and source_snapshots.py",
      "result": "passed",
      "summary": "Confirmed required revision lineage, terminal closure, bounded coverage, source hashes, and immutable snapshot semantics."
    },
    {
      "command": "git status / tests / git commit",
      "result": "not-run",
      "summary": "No shell or git execution tool was available to this child research run."
    }
  ],
  "validationOutput": [
    "Verdict cross-checked against every endpoint requested by the task and the closest discovered historical APIs bak_basic, stock_st, and bse_mapping.",
    "Only first-party Tushare sources and local Backtest evidence were retained; secondary sources were dropped.",
    "Public API probe contained no token or sensitive data."
  ],
  "residualRisks": [
    "Authenticated response headers/rows and cryptographic hashes were not captured because no token or shell hashing capability was available.",
    "A private Tushare enterprise artifact or contract not visible on the public first-party surface could alter the verdict.",
    "Commit hash is unavailable because this child run could not execute git."
  ],
  "noStagedFiles": true,
  "diffSummary": "Added one authoritative research brief; no registry/provider qualification edits and no tests changed.",
  "reviewFindings": [
    "critical blocker: Tushare public artifacts do not supply July-2026 historical-as-of listing state plus correction lineage, terminal completeness, and immutable vendor version/checksum.",
    "high: bak_basic offers partial daily historical membership from 2016 but lacks status/absence semantics and revision closure.",
    "critical: Tushare service agreement expressly disclaims completeness and timeliness guarantees."
  ],
  "manualNotes": "Requested repository report/commit must be performed by the parent; runtime output-path override required this child to write only /tmp/backtest-g12k-authority-v2/research.md."
}
```
