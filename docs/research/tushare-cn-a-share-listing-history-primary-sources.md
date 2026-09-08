# Tushare China A-share listing-history primary sources

## Summary

The smallest honest authority is a **fixed-singleton, source-bounded presence/identity slice**, not a provider-qualified listing lifecycle: use an exact `stock_basic` capture for the current identity/status anchor, an exact `bak_basic(trade_date=20240102, ts_code=000001.SZ)` capture for provider-returned historical-day presence, and the full `namechange(ts_code=000001.SZ)` response for returned effective-name intervals. Keep `trade_cal`, `suspend_d`, `dividend`, and `adj_factor` as separate calendar, trading-availability, corporate-action, and derived-adjustment evidence; none closes listing-history completeness, revision finality, or corporate-action lifecycle.

## Findings

1. **Blocker — the existing G12L claim is broader than the official interfaces can honestly support.** `docs/implementation/acceptance-matrix.md` keeps `G12L-TUSHARE-CN-A-SHARE-DAILY-LISTING-V1` `DRAFT / BLOCKED` on provider revision, listing history, and corporate-action authority. `docs/implementation/plans/g12/g12l-tushare-cn-a-share-daily-listing-v1.md` already freezes `000001.SZ` and `2024-01-02`, while `docs/research/g12l-tushare-listing-corporate-action-revision-authority-v1.md` correctly leaves historical-listing, action-lifecycle, and revision closure false. Accepted G12I proves only its exact July-2026 price/availability/publication slice; accepted G12K proves exact daily-row presence plus one 96-row dividend response, explicitly not historical listing, survivorship, completeness, absence, or action lifecycle. Severity: **blocker** for the current broad G12L name; **no blocker** for a narrower additive source-bounded acceptance slice.

2. **`stock_basic` is the smallest current identity/status anchor, not historical-as-of authority.** Official endpoint: `stock_basic`. Inputs: `ts_code`, `name`, `market`, `list_status`, `exchange`, `is_hs`; `list_status` is `L` listed, `D` delisted, `P` suspended listing, `G` approved/not yet traded, default `L`. Relevant outputs: `ts_code`, `symbol`, `name`, `fullname`, `market`, `exchange`, `curr_type`, `list_status`, `list_date`, `delist_date`. Limit: 6,000 rows/request; permission: 2,000 points, 50 requests/minute; documentation recommends one pull and local storage. No `as_of`, pagination parameter, update cadence, immutable revision ID, checksum, correction log, supersession link, completeness marker, or finality guarantee is documented. The page’s sample shows `000001.SZ`, `平安银行`, `list_date=19910403`, but a documentation sample is not a current captured response. [Tushare `stock_basic`](https://tushare.pro/document/2?doc_id=25)

3. **`bak_basic` is the narrowest documented improvement for the target-date history claim.** Official endpoint: `bak_basic`, described as a historical daily stock list, with data from 2016. Inputs: `trade_date`, `ts_code`. Relevant outputs: `trade_date`, `ts_code`, `name`, `industry`, `area`, `list_date` plus fundamentals. Limit: 7,000 rows/request; history may be iterated by date; formal access requires 5,000 points. No cadence, pagination/offset, correction history, completeness guarantee, immutable revision, or finality guarantee is documented. A returned row for exact request `trade_date=20240102, ts_code=000001.SZ` can support only: “Tushare returned this singleton in its historical daily list at acquisition time.” It cannot prove uninterrupted listing since 1991, exchange-official status, or that zero rows means absence. [Tushare `bak_basic`](https://tushare.pro/document/2?doc_id=262)

4. **`namechange` supplies returned identity intervals, not listing-status intervals.** Official endpoint: `namechange`; inputs `ts_code`, `start_date`, `end_date`; outputs `ts_code`, `name`, `start_date`, `end_date`, `ann_date`, `change_reason`. The page documents no row limit, pagination, cadence, availability window, revision/correction history, completeness, or finality guarantee. Preserve the full singleton response and select the unique returned interval covering `2024-01-02`; do not infer listing, continuous tradability, or complete corporate history from it. [Tushare `namechange`](https://tushare.pro/document/2?doc_id=100)

5. **Daily suspension is not `stock_basic.list_status=P`.** `suspend_d` is daily halt/resumption information: inputs `ts_code`, `trade_date`, `start_date`, `end_date`, `suspend_type` (`S`/`R`); outputs `ts_code`, `trade_date`, `suspend_timing`, `suspend_type`; update cadence is only “irregular.” No limit, pagination, completeness, correction, or finality guarantee is stated. It can qualify a returned halt/resumption row, but zero rows cannot be promoted to authoritative “not suspended.” It must not be used to rewrite the separate `stock_basic` “suspended listing” status. [Tushare `suspend_d`](https://tushare.pro/document/2?doc_id=214)

6. **`trade_cal` proves venue-calendar state only.** Official endpoint: `trade_cal`; inputs `exchange`, `start_date`, `end_date`, `is_open`; outputs `exchange`, `cal_date`, `is_open`, `pretrade_date`; permission is 2,000 points. The page states no row limit, pagination, update cadence, correction history, or finality guarantee. The exact accepted SZSE calendar row may establish whether `2024-01-02` was an SZSE trading day, but not whether `000001.SZ` was listed or tradable. [Tushare `trade_cal`](https://tushare.pro/document/2?doc_id=26)

7. **Corporate-action lifecycle is a sibling authority, not part of listing authority.** `dividend` requires at least one of `ts_code`, `ann_date`, `record_date`, `ex_date`, `imp_ann_date`; outputs include `end_date`, announcement/record/ex/pay/listing/implementation dates, `div_proc`, stock/cash distribution fields, `base_date`, and `base_share`. The page states a 2,000-point permission threshold but no row limit, pagination, update cadence, revision trail, lifecycle completeness, or terminal finality. The accepted G12K full singleton response is therefore a frozen returned set, not proof that all actions/revisions are complete. `adj_factor` is a Tushare-produced derived factor and may corroborate price-adjustment behavior, but it is not an action-event ledger and cannot close dividend lifecycle. [Tushare `dividend`](https://tushare.pro/document/2?doc_id=103) [Tushare `adj_factor`](https://tushare.pro/document/2?doc_id=28)

8. **`stock_company` and the SZSE list are useful identity corroboration but unnecessary for the minimum Tushare slice.** `stock_company(ts_code|exchange)` returns company identity fields including `com_name`, `com_id`, and `exchange`, with a 4,500-row/request limit and 120-point permission threshold, but no historical-as-of/revision guarantees. The official SZSE stock list identifies code `000001`, 平安银行, Main Board, listing date `1991-04-03`; it is good first-party corroboration, not a substitute for preserving the exact Tushare responses under test. [Tushare `stock_company`](https://tushare.pro/document/2?doc_id=112) [SZSE stock list](https://investor.szse.cn/market/product/stock/list/index.html)

9. **Claims unavailable from current snapshots must remain false/null.** Current accepted captures cannot establish: provider-global or exchange-global completeness; uninterrupted listing from `1991-04-03`; historical `list_status` as of `2024-01-02`; authoritative absence from a zero-row response; all name changes; all suspensions/resumptions; all dividends or other corporate actions; correction/revision history; immutable provider publication identity; terminal finality; survivorship-free universe membership; decision grade; live/deployment authority. Locally computed hashes attest only preserved bytes, not provider-declared finality.

## Recommended smallest acceptance slice

Create an **additive, fixed-singleton source-bounded acceptance** (do not claim the broad G12L lifecycle):

- preserve exact raw bytes and one acquisition receipt for:
  - `stock_basic(ts_code='000001.SZ', list_status='L', fields='ts_code,symbol,name,fullname,market,exchange,curr_type,list_status,list_date,delist_date')`;
  - `bak_basic(trade_date='20240102', ts_code='000001.SZ', fields='trade_date,ts_code,name,list_date')`;
  - `namechange(ts_code='000001.SZ', fields='ts_code,name,start_date,end_date,ann_date,change_reason')`;
- reuse the already accepted exact SZSE `trade_cal` evidence and accepted G12K full dividend response by immutable identity; do not recapture them merely to bundle concepts together;
- omit `suspend_d` unless the acceptance claim explicitly includes target-day trading availability; if included, qualify only returned rows and retain zero-row non-authority;
- require equality checks across `ts_code`, exchange/code mapping, `list_date`, and the target-date name interval; fail closed on zero/multiple `bak_basic` rows or zero/multiple covering name intervals;
- freeze: `provider_revision_id=null`, `revision_closure_complete=false`, `historical_listing_lifecycle_qualified=false`, `corporate_action_lifecycle_qualified=false`, `absence_authority=false`, `decision_grade_eligible=false`, `deployment_authorized=false`.

The accepted statement should be only: **at the recorded acquisition time, Tushare returned a current listed identity row for `000001.SZ`, a matching historical-list row for `2024-01-02`, and a name interval covering that date; separately accepted calendar and dividend snapshots remain bounded observations.**

## Sources

- Kept: [Tushare `stock_basic`](https://tushare.pro/document/2?doc_id=25) — official identity/status schema, limits, permissions.
- Kept: [Tushare `bak_basic`](https://tushare.pro/document/2?doc_id=262) — official historical daily-list endpoint and 2016 boundary.
- Kept: [Tushare `namechange`](https://tushare.pro/document/2?doc_id=100) — official historical-name intervals.
- Kept: [Tushare `suspend_d`](https://tushare.pro/document/2?doc_id=214) — official daily halt/resume semantics and irregular cadence.
- Kept: [Tushare `trade_cal`](https://tushare.pro/document/2?doc_id=26) — official venue-calendar schema.
- Kept: [Tushare `dividend`](https://tushare.pro/document/2?doc_id=103) and [`adj_factor`](https://tushare.pro/document/2?doc_id=28) — official action fields versus derived factor.
- Kept: [Tushare `stock_company`](https://tushare.pro/document/2?doc_id=112) and [SZSE stock list](https://investor.szse.cn/market/product/stock/list/index.html) — first-party identity corroboration.
- Dropped: blogs, SDK examples outside official Tushare documentation, data aggregators, and search snippets from non-official domains — not primary authority.

## Gaps

No cited official page documents immutable revisions, correction/supersession history, terminal publication closure, response completeness, or historical-as-of `stock_basic`. A real `bak_basic` target-date capture is not identified in the accepted evidence reviewed; until captured and independently reviewed, even the narrow historical-day presence statement remains unaccepted.
