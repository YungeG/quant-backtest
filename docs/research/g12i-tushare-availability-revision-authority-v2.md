# Research: G12I Tushare China A-share daily availability/revision authority v2

## Summary

**Verdict: BLOCKED; the G12I availability/revision blocker cannot be closed from first-party Tushare documentation plus the current Backtest captures.** Tushare documents enough to build a conservative finite acquisition for `daily`, `trade_cal`, and `suspend_d`, but it does not document daily-bar correction history, immutable provider revision IDs/checksums, revision terminality, authoritative `NO_TRADES` or `SOURCE_OUTAGE` declarations, or stable pagination-envelope semantics. The exact additional credential is an environment-only `TUSHARE_TOKEN` whose account can call `daily` and has at least 2,000 points for `trade_cal`; a new credentialed July-2026 raw capture is also needed because the existing accepted evidence covers only `000001.SZ / 2024-01-02`.

## Findings

1. **BLOCKER — Tushare supplies no immutable daily revision/correction closure.** The official `daily` schema has business fields only; no revision ID, correction flag, supersession link, provider checksum, publication timestamp, or terminal marker is documented. Tushare’s FAQ explicitly documents `update_flag` for revised *financial* statements, showing that revision semantics are documented where they exist, but no equivalent is documented for `daily`. The official ChangeLog records interface/content changes (including the 2026-07-06 addition of `ah_vol` and `ah_amount`) rather than per-row correction lineage. Therefore repeated byte captures can prove “what this request returned at acquisition time,” not that no later correction exists. [A-share daily](https://tushare.pro/document/2?doc_id=27) [FAQ](https://tushare.pro/document/1?doc_id=122) [ChangeLog](https://tushare.pro/document/1?doc_id=9)

2. **BLOCKER — Tushare expressly does not guarantee completeness, accuracy, or timeliness.** The official data-service agreement says Tushare cannot guarantee data accuracy, correctness, completeness, integrity, or timeliness and does not guarantee uninterrupted service. This prevents treating undocumented provider state or silence as immutable closure authority. [Tushare data-service agreement](https://tushare.pro/document/1?doc_id=405)

3. **HIGH — A finite July-2026 availability capture is possible, but only a subset of reasons is authoritative.** Use the official July example scope `000001.SZ / 2026-07-07` (the `daily` page says the new after-hours fields begin 2026-07-06) and query exact point scopes latest-first after the documented daily ingestion window. A returned exact `daily` row supports availability at capture time. An exact `trade_cal` row with `is_open=0` supports `NO_SESSION`. On an open date, an exact `suspend_d` `S` row can support `SUSPENDED`; `suspend_timing=null` is the conservative full-day case, while a populated interval supports only that intraday interval. [A-share daily](https://tushare.pro/document/2?doc_id=27) [Trade calendar](https://tushare.pro/document/2?doc_id=26) [Daily suspension/resumption](https://tushare.pro/document/2?doc_id=214)

4. **HIGH — `NO_TRADES`, `MISSING`, and `SOURCE_OUTAGE` remain indistinguishable for an absent open-day row.** Tushare documents that suspended periods have no `daily` data, but it does not define an absent non-suspended row as “no trades.” It also provides no per-request source-outage classification or public incident/status API. The FAQ says timeouts may result from rate limits, proxy configuration, or network conditions, so a timeout/HTTP failure is acquisition evidence, not provider authority for `SOURCE_OUTAGE`. A zero-volume `daily` row could be preserved as observed data, but the public daily page does not define `vol=0, amount=0` as the terminal `NO_TRADES` reason required by G12I. [A-share daily](https://tushare.pro/document/2?doc_id=27) [FAQ](https://tushare.pro/document/1?doc_id=122)

5. **HIGH — Existing Backtest evidence is exact but intentionally non-closing.** `tests/fixtures/market_data/providers/tushare/cn-a-share-daily-listing-v1/daily.json` freezes one exact 2024 daily response with independently computed hash `sha256:c2950a35c093b983e538f97830b7b3fcb0bba1a7dac98a17bd20f6db9296f846`; `tests/fixtures/market_data/providers/tushare/cn-a-share-trade-calendar-v1/trade-calendar.json` freezes one exact open-day response with hash `sha256:aead455c7bb4ab5ff3966fb06c8c5b640b537767f38ebf99249fad05a8211bf9`. Their receipts set `declared_sha256=null`, `decision_grade_eligible=false`, and `deployment_authorized=false`. The accepted purpose-scope fixture also keeps both `availability_closure_complete=false` and `revision_closure_complete=false`. These are Backtest content identities, not provider-declared immutable versions.

6. **HIGH — Current `daily` and `trade_cal` acquisition validators do not enforce terminal-envelope semantics.** `tools/acquisition/cn_a_share_tushare.py::_rows` validates `code`, `fields`, and `items` but ignores `request_id`, `has_more`, and `count`; `tools/acquisition/cn_a_share_tushare_trade_calendar.py` reuses it. Thus the existing exact captures happened to contain `has_more=false`, but the acquisition contract does not require it. `tools/acquisition/cn_a_share_tushare_authority.py::_authority_rows` does require `has_more=false` and `count=0`, but the public interface docs do not define those envelope fields or prove revision finality.

7. **MEDIUM — `count=0` is demonstrably not a returned-row count and must not be treated as completeness proof.** The committed first-party responses have `count=0` while containing 1 `stock_basic` row, 4 `namechange` rows, 3 `adj_factor` rows, and 1 `daily` row. `has_more=false` may be useful as response-page exhaustion at acquisition time, but neither it nor `count=0` is documented as revision/correction terminality. See `tests/fixtures/market_data/providers/tushare/cn-a-share-authority-v1/*.json` and `tests/fixtures/market_data/providers/tushare/cn-a-share-daily-listing-v1/daily.json`.

8. **MEDIUM — Point requests avoid the documented 6,000-row daily cap but do not solve absence or revision semantics.** Tushare documents at most 6,000 rows per `daily` request and recommends full-market acquisition by `trade_date`. The smallest reliable G12I experiment is instead one instrument and one date per request, so expected cardinality is zero or one. This avoids pagination pressure, but an empty result on an open, non-suspended date still cannot be assigned among `NO_TRADES`, `MISSING`, and `SOURCE_OUTAGE`. [A-share daily](https://tushare.pro/document/2?doc_id=27)

9. **MEDIUM — Update timing is a polling lower bound, not finality.** The `daily` page says ingestion occurs on trading days from 15:00–16:00 China time, while the official permissions page says 15:00–17:00. Use the more conservative 17:00 bound for capture timing. `suspend_d` is documented as updated “irregularly,” and `trade_cal` has no update/finality schedule on its interface page. No page promises that data is immutable after those times. [A-share daily](https://tushare.pro/document/2?doc_id=27) [Permissions](https://tushare.pro/document/1?doc_id=108) [Daily suspension/resumption](https://tushare.pro/document/2?doc_id=214)

10. **BLOCKER — Exact missing artifact for closure.** Required: environment-only `TUSHARE_TOKEN` with sufficient account permission; exact raw response bytes and a no-clobber receipt for `daily(ts_code=000001.SZ,start_date=20260707,end_date=20260707)`, `trade_cal(exchange=SZSE,start_date=20260707,end_date=20260707)`, and `suspend_d(ts_code=000001.SZ,trade_date=20260707,suspend_type=S)` acquired after 17:00 Asia/Shanghai; unique-key JSON validation; request scope, attempt count, acquisition timestamp, response byte hashes, and G12A snapshot identity. Even that capture can close only acquisition-time `AVAILABLE`/`NO_SESSION`/`SUSPENDED` classification for the exact slice. Full G12I revision closure additionally requires a first-party immutable revision/checksum/correction-terminal artifact that Tushare’s public docs and current responses do not provide.

## Proposed finite classification contract

| Exact observation for `000001.SZ / 2026-07-07` | Conservative G12I result | Authority limit |
| --- | --- | --- |
| Exact `daily` row returned | available at acquisition time | Not immutable; later correction may occur |
| Exact `trade_cal.is_open=0` | `NO_SESSION` | Calendar itself has no documented revision finality |
| `is_open=1`, exact `suspend_d` `S`, `suspend_timing=null`, no daily row | `SUSPENDED` | Only at acquisition time; `suspend_d` updates irregularly |
| `is_open=1`, exact intraday suspension interval | classify only that interval as suspended | Must not classify the entire daily bucket |
| `is_open=1`, no suspension row, exact daily row with zero volume | preserve observed zero-volume row | Do not promote to `NO_TRADES` without first-party semantic authority |
| `is_open=1`, no suspension row, no daily row | unresolved (`MISSING` / `NO_TRADES` / `SOURCE_OUTAGE`) | Blocker remains |
| HTTP timeout, 429, 5xx, or connection error | acquisition failure | Not source-outage authority |

## Backtest evidence reviewed

- Plans: `docs/implementation/plans/g12/g12i.md`, `g12i-tushare-cn-a-share-daily-purpose-scope-v1.md`, `g12l-tushare-cn-a-share-daily-listing-v1.md`, `g12l-tushare-cn-a-share-authority-acquisition-v1.md`.
- Research: `docs/research/g12i-price-availability-revision-coverage.md`, `g12l-tushare-cn-a-share-daily-listing-v1.md`, `g12l-tushare-listing-corporate-action-revision-authority-v1.md`, `g12l-cn-a-share-daily-event-time-v1.md`.
- Tools: `tools/acquisition/cn_a_share_tushare.py`, `cn_a_share_tushare_trade_calendar.py`, `cn_a_share_tushare_authority.py`.
- Fixtures/receipts: purpose-scope, daily, trade-calendar, stock-basic, namechange, adj-factor, dividend, and acquisition receipts under `tests/fixtures/market_data/providers/tushare/`.

## Sources

- Kept: [A-share daily / `daily`](https://tushare.pro/document/2?doc_id=27) — official schema, 15:00–16:00 ingestion, suspension omission, 6,000-row limit, and July-2026 field change.
- Kept: [Trade calendar / `trade_cal`](https://tushare.pro/document/2?doc_id=26) — official open/closed-day fields and exact filters.
- Kept: [Daily suspension/resumption / `suspend_d`](https://tushare.pro/document/2?doc_id=214) — official suspension reason and irregular update cadence.
- Kept: [Tushare ChangeLog](https://tushare.pro/document/1?doc_id=9) — official 2026-07-06 daily schema change and evidence that interface evolution is not version-bound in responses.
- Kept: [Tushare FAQ](https://tushare.pro/document/1?doc_id=122) — official timeout ambiguity and contrasting financial `update_flag` revision semantics.
- Kept: [Permissions/update table](https://tushare.pro/document/1?doc_id=108) — conservative 15:00–17:00 daily update window and credential threshold.
- Kept: [Tushare data-service agreement](https://tushare.pro/document/1?doc_id=405) — explicit non-guarantee of completeness, accuracy, timeliness, and uninterrupted service.
- Dropped: all secondary blogs, mirrors, Q&A sites, and vendor commentary — prohibited by scope and unnecessary.
- Dropped: search snippets without a stable official document URL — insufficient authority.
- Dropped: unauthenticated `api.waditu.com` probe — fetch environment blocked the resolved fake-IP/TUN range, and a GET would not reproduce the required credentialed POST anyway.

## Gaps

- No usable `TUSHARE_TOKEN` was available to this child run, and the tool set cannot inspect environment credentials or issue the required POST safely.
- No July-2026 credentialed `daily`/`trade_cal`/`suspend_d` response bytes, headers, receipt, or hash were captured.
- No first-party Tushare status/incident artifact for an exact source outage was found.
- No first-party immutable daily revision ID, declared checksum, signed manifest, correction ledger, supersession graph, or terminal-closure protocol was found.
- Git diff, link checker, tests, gitleaks, staging state, commit, and commit hash are parent-owned and were not runnable with this child’s read/write/web-only tools.

## Recommended parent action

Do not change shared registry or qualification state. If a suitable token is available, add only a bounded no-clobber acquisition/evidence slice for the three exact July-2026 point requests above, preserving all closure flags as false. This can narrow availability evidence but cannot close revision authority unless Tushare supplies a new first-party immutable correction-terminal artifact.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Concrete BLOCKER/HIGH/MEDIUM findings cite exact repository paths, existing fixture hashes, and first-party Tushare URLs."
    }
  ],
  "changedFiles": [
    "/tmp/backtest-g12i-authority-v2/research.md"
  ],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "read required G12I/G12L plans, acquisition tools, and Tushare fixtures/receipts",
      "result": "passed",
      "summary": "Reviewed all supervisor-supplied local evidence paths plus the existing daily fixture and event-time research."
    },
    {
      "command": "first-party web research and fetch of official Tushare daily, trade_cal, suspend_d, ChangeLog, FAQ, permissions, and service agreement",
      "result": "passed",
      "summary": "Only official tushare.pro sources were retained."
    },
    {
      "command": "git diff / link validation / pytest / gitleaks / git status / git commit",
      "result": "not-run",
      "summary": "Unavailable in this child tool set; parent owns git validation and commit."
    }
  ],
  "validationOutput": [
    "Official links fetched successfully: doc_id=27, 26, 214, 9, 122, 108, 405.",
    "Existing Backtest evidence confirms provider-declared checksums are null and closure/qualification flags remain false.",
    "api.waditu.com unauthenticated fetch was blocked by the web tool's fake-IP/SSRF guard; no credential was exposed."
  ],
  "residualRisks": [
    "No July-2026 credentialed raw API capture exists in this run.",
    "An absent open-day daily row cannot be authoritatively distinguished among NO_TRADES, MISSING, and SOURCE_OUTAGE.",
    "No immutable provider revision/checksum/correction-terminal authority was found.",
    "Repository staging state, secret scan, diff, tests, commit, and commit hash remain unverified by this child."
  ],
  "noStagedFiles": false,
  "diffSummary": "Research-only output written to the authoritative runtime path; no repository qualification or registry edits were made by this child.",
  "reviewFindings": [
    "blocker: Tushare daily exposes no immutable revision/checksum/correction-terminal authority.",
    "high: tools/acquisition/cn_a_share_tushare.py::_rows does not enforce unique-key or has_more/count terminal-envelope checks; trade-calendar acquisition reuses it.",
    "high: open-day absence cannot distinguish NO_TRADES, MISSING, or SOURCE_OUTAGE from first-party Tushare evidence.",
    "medium: provider response count=0 coexists with nonzero items and is not row-count/completeness authority."
  ],
  "manualNotes": "Parent must run link/diff/tests/gitleaks/git-status validation and create any requested repository report commit. Final verdict: BLOCKED."
}
```
