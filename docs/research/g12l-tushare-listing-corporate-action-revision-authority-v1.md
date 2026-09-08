# G12L Tushare listing, corporate-action, and revision authority v1

## Scope and decision

This brief covers only `000001.SZ` for trading date `2024-01-02` and uses only the four official Tushare interface pages listed below. The documented interfaces can support a finite, acquisition-time-bound candidate capture for listing dates, historical names, adjacent adjustment factors, and target-date dividends. They do **not** document immutable provider revision IDs, provider-declared checksums, correction history, supersession links, or a terminal-closure protocol. G12L historical-listing, corporate-action-lifecycle, revision-closure, decision-grade, and deployment qualification therefore remain false.

## Primary sources

1. Tushare, **股票基础信息 / `stock_basic`**: <https://tushare.pro/document/2?doc_id=25>
2. Tushare, **复权因子 / `adj_factor`**: <https://tushare.pro/document/2?doc_id=28>
3. Tushare, **分红送股 / `dividend`**: <https://tushare.pro/document/2?doc_id=103>
4. Tushare, **股票曾用名 / `namechange`**: <https://tushare.pro/document/2?doc_id=100>

## Documented facts

### `stock_basic`

- Purpose: current stock basic information, including stock code, name, listing date, and delisting date.
- Inputs include `ts_code`, `name`, `market`, `list_status`, `exchange`, and `is_hs`.
- `list_status` values are documented as `L` listed, `D` delisted, `P` suspended listing, and `G` approved but not yet traded; the default is `L`.
- Relevant outputs are `ts_code`, `symbol`, `name`, `area`, `industry`, `market`, `exchange`, `list_status`, `list_date`, and `delist_date`.
- Limit: at most 6,000 rows per request.
- Permission/rate: 2,000 points and 50 requests per minute.
- The page recommends fetching this basic-information interface once and retaining it locally. It does not state an immutable publication revision, checksum, correction log, historical-as-of parameter, or update schedule.

### `namechange`

- Purpose: historical security-name change records.
- Inputs are `ts_code`, `start_date`, and `end_date`.
- Outputs are `ts_code`, `name`, `start_date`, `end_date`, `ann_date`, and `change_reason`.
- The documented rows form effective-name intervals through `start_date` and optional `end_date`.
- The page states no row limit, update cadence, immutable revision ID, checksum, correction history, or terminal-closure field.

### `adj_factor`

- Purpose: Tushare-produced stock adjustment factors; one stock's complete history or one date's market-wide factors can be requested.
- Inputs are `ts_code`, `trade_date`, `start_date`, and `end_date`.
- Outputs are exactly `ts_code`, `trade_date`, and `adj_factor`.
- Update cadence: Tushare documents completion of the current day's factor ingestion before market open, around 09:15–09:20.
- Permission: 2,000 points; 5,000 points or more permits higher-frequency access.
- The page does not expose an immutable revision ID, checksum, correction history, supersession field, or terminal-closure marker. It also does not state a row limit on the cited page.

### `dividend`

- Purpose: dividend and bonus-share data.
- At least one of `ts_code`, `ann_date`, `record_date`, `ex_date`, or `imp_ann_date` must be supplied.
- Outputs are `ts_code`, `end_date`, `ann_date`, `div_proc`, `stk_div`, `stk_bo_rate`, `stk_co_rate`, `cash_div`, `cash_div_tax`, `record_date`, `ex_date`, `pay_date`, `div_listdate`, `imp_ann_date`, `base_date`, and `base_share`.
- Permission: at least 2,000 points.
- The page states no request row limit or update cadence and exposes no immutable revision ID, checksum, correction history, supersession field, or terminal-closure marker.

## Inferences for the exact Backtest slice

The following are Backtest interpretations, not claims made by the provider documentation.

### Historical listing

A captured `stock_basic(ts_code=000001.SZ)` row can provide a **candidate interval** from `list_date` through optional `delist_date`. If `list_date <= 20240102` and `delist_date` is null or later than `20240102`, the captured current metadata is consistent with the instrument being listed on the target date.

That is not a historical-as-of status snapshot. The interface has no `as_of`, provider revision, or correction-history parameter, and the page describes current basic information. Therefore:

```text
historical_listing_status_qualified=false
```

A captured `namechange(ts_code=000001.SZ)` response can independently identify the unique effective name interval covering `20240102`. It proves a returned historical name interval, not listing status.

### Corporate actions

A bounded capture should use:

```text
adj_factor(
  ts_code=000001.SZ,
  start_date=20231229,
  end_date=20240103,
)

dividend(
  ts_code=000001.SZ,
  ex_date=20240102,
)
```

The adjacent adjustment-factor rows can show whether the captured factor changes across previous/target/next trading dates. An exact target-date dividend response can show which dividend rows the provider returned for that ex-date; zero rows are still a finite captured response.

Neither observation proves the complete corporate-action lifecycle. Adjustment factors are Tushare-produced derived data, and the documentation provides no revision/correction closure. A zero-row dividend response means only “no matching row returned by this request at this acquisition time,” not permanent absence. Therefore:

```text
corporate_action_lifecycle_qualified=false
```

### Revision and correction authority

Across all four documented interfaces, output schemas contain business data and request filters only. None documents:

- immutable provider publication/revision IDs;
- provider-declared response checksums;
- correction or restatement history;
- supersedes/superseded-by relationships;
- a query for all revisions;
- a terminal or completeness marker.

This is an assessment of the documented public interface, not a claim that Tushare has no internal governance metadata. Backtest cannot treat undocumented internal state as authority. A captured HTTP `request_id`, if present in a response envelope, is request correlation rather than a documented immutable data revision. Therefore:

```text
provider_revision_id=null
revision_closure_complete=false
```

## Recommended bounded acquisition contract

Preserve exact raw response bytes for:

1. `stock_basic(ts_code=000001.SZ)`;
2. `namechange(ts_code=000001.SZ)`;
3. `adj_factor(ts_code=000001.SZ, start_date=20231229, end_date=20240103)`;
4. `dividend(ts_code=000001.SZ, ex_date=20240102)`.

Bind all four responses to one acquisition timestamp and candidate G12A snapshot. Record independently computed content hashes, but keep provider-declared checksum fields null. Keep token material environment-only and absent from responses, receipts, logs, and committed artifacts. Fix all qualifications false:

```text
provider_revision_id=null
revision_closure_complete=false
historical_listing_status_qualified=false
corporate_action_lifecycle_qualified=false
decision_grade_eligible=false
deployment_authorized=false
```

This capture can narrow G12L evidence gaps, but it cannot by itself close G12L, G12I, G12K, G12M, decision-grade, or deployment gates.
