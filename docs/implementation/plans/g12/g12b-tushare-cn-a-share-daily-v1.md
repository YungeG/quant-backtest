---
id: G12B-TUSHARE-CN-A-SHARE-DAILY-V1
status_source: ../../acceptance-matrix.md
owner: market-bundle-builder Tushare daily normalization
produces:
  - TushareCnAShareDailyRawBar
  - exact source-to-raw-bar trace
  - execution-reference projection
  - valuation projection
consumes:
  - G12A SourceSnapshot
  - frozen Tushare daily response
  - frozen A-share daily BarBucket
  - frozen lexical numeric mapping
depends_on:
  contract: [G12A, G12B, G12G]
  evidence:
    - g12l-tushare-cn-a-share-daily-listing-v1
    - g12l-cn-a-share-daily-event-time-v1
    - g12l-cn-a-share-daily-numeric-mapping-v1
fan_out: [G12C-TUSHARE-CN-A-SHARE-DAILY-V1, G12I, G12M-CN-A-SHARE]
---

# G12B Tushare China A-share Daily Raw Bar and Purpose Projection v1

## Status

`IMPLEMENTED / ACCEPTANCE_PENDING`. The internal normalizer and focused contract
suite implement the exact `000001.SZ / 2024-01-02` source slice. Independent review
fixes are applied; final reviewer/full-repository acceptance remains pending. This
status does not authorize G12C/D publication, historical listing status, provider
correction closure, corporate actions, decision-grade use, or deployment.

## Outcome and interface

```text
normalize_tushare_cn_a_share_daily_v1(
  snapshot: SourceSnapshot,
  request: TushareCnAShareDailyNormalizationRequest,
) -> TushareCnAShareDailyNormalizationOutcome
```

The outcome contains exactly one result or one failure. A successful result contains
the purpose-free raw Bar, exact trace, and both explicit projections:

```text
Tushare daily source row
→ TushareCnAShareDailyRawBar        # no price_purpose
  ├─→ TushareCnAShareDailyExecutionReference
  └─→ TushareCnAShareDailyValuation
```

No generic daily `MarketEvent` is emitted. G12C/D owns later stream publication after
revision/listing/coverage evidence is sufficient.

## Frozen request

```text
TushareCnAShareDailyNormalizationRequest@1 = {
  schema_version: 1,
  snapshot_id: sha256,
  provenance_hash: sha256,
  member_key: "response/daily.json",
  member_content_hash: sha256,
  instrument_id: InstrumentId("xshe", "000001"),
  provider_trade_date: "20240102",
  bucket: BarBucket,
}
```

Canonical body is `{type="tushare_cn_a_share_daily_normalization_request", ...all
fields above...}` and `request_hash = canonical_sha256(body)`.

Both `snapshot_id` and `provenance_hash` are mandatory. Snapshot/content identities do
not bind acquisition time; provenance identity does. Availability is never caller
supplied and is derived from the selected member only.

## Exact JSON-number authority

Use one private numeric-token type and `json.loads` hooks for both `parse_int` and
`parse_float`. JSON strings remain ordinary `str` and therefore cannot masquerade as
numeric tokens. `parse_constant` rejects NaN/Infinity. Duplicate object keys fail.

Every numeric token must match:

```regex
-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?
```

Exponent notation, leading plus, leading zeroes, trailing decimal point, JSON numeric
strings, booleans, nulls, and non-finite constants are rejected. Raw token lexemes are
preserved exactly.

The response wrapper and data schema are exact:

```text
top-level keys = ("request_id", "code", "data", "msg", "detail")
request_id = non-empty canonical JSON string
code = exact integer 0
msg = exact empty string
detail = JSON string

data keys = ("fields", "items", "has_more", "count")
has_more = exact false
count = exact integer 0
fields = (
  "ts_code", "trade_date", "open", "high", "low", "close",
  "pre_close", "change", "pct_chg", "vol", "amount"
)
items = exactly one row
```

Extra/missing keys, wrong types, nonzero provider code, nonempty message, pagination, or
count mismatch are `SOURCE_SCHEMA_MISMATCH`. `ts_code` and `trade_date` are JSON
strings. The remaining nine values are tagged JSON number tokens.

## Frozen raw Bar schema

```text
TushareCnAShareDailyRawBar@1 = {
  instrument_id: InstrumentId,
  provider_ts_code: "000001.SZ",
  provider_trade_date: str,
  bucket: BarBucket,
  available_time: UtcInstant,
  open_lexeme: str,
  high_lexeme: str,
  low_lexeme: str,
  close_lexeme: str,
  pre_close_lexeme: str,
  change_lexeme: str,
  pct_change_lexeme: str,
  volume_lots_lexeme: str,
  amount_thousand_cny_lexeme: str,
  open_price: Price,
  high_price: Price,
  low_price: Price,
  close_price: Price,
  pre_close_price: Price,
  change_units: int,
  change_scale: Scale(2),
  pct_change: Rate(basis="percent", scale=4),
  volume: Quantity(scale=0, basis=instrument),
  amount: Money(currency="CNY", scale=0),
  source_record_hash: sha256,
  limitations: tuple[str, ...],
  decision_grade_eligible: false,
  deployment_authorized: false,
}
```

Canonical body is `{type="tushare_cn_a_share_daily_raw_bar", schema_version=1,
...all fields above...}`. `raw_bar_hash = canonical_sha256(body)`. The constructor
recomputes `source_record_hash` from retained `provider_ts_code`, trade date, and all
nine numeric lexemes; a caller-supplied hash is never trusted independently.

Fixed limitations, canonical-sorted:

- `corporate_actions_unproven`;
- `historical_listing_status_unproven`;
- `late_historical_availability`;
- `provider_revision_closure_unproven`.

The raw Bar contains no `price_purpose`, settlement/adjusted price, listing status,
corporate-action adjustment, funding, margin, or liquidation field.

## Numeric mapping and invariants

- price/change: at most 2 decimal places, mapped to scale 2;
- percentage change: at most 4 decimal places, mapped to scale 4;
- volume: at most 2 decimal lots, multiplied by 100 shares/lot, scale 0;
- amount: at most 3 decimal thousand-CNY, multiplied by 1000, scale 0.

```text
0 < low <= open <= high
0 < low <= close <= high
pre_close > 0
close - pre_close == change
volume >= 0
amount >= 0
```

Provider `pct_chg` remains rounded source evidence and is not recomputed. Mapping uses
integer string operations only; binary float and ambient Decimal context are not
authorities.

## Source-record and trace identities

After schema/type validation, define:

```text
source_record_hash = canonical_sha256({
  type: "tushare_cn_a_share_daily_source_record",
  schema_version: 1,
  fields: exact fields tuple,
  text_values: (ts_code, trade_date),
  numeric_lexemes: exact nine-token tuple,
})
```

```text
TushareCnAShareDailySourceTrace@1 = {
  snapshot_id: sha256,
  provenance_hash: sha256,
  source_key: str,
  member_key: str,
  member_content_hash: sha256,
  record_index: 0,
  source_record_hash: sha256,
  raw_bar_hash: sha256,
  revision_id: member_content_hash,
  supersedes_revision_id: null,
  revision_closure_complete: false,
}
```

Canonical body is `{type="tushare_cn_a_share_daily_source_trace",
schema_version=1, ...all fields above...}` and `trace_hash = canonical_sha256(body)`.

This is a finite causal limit: the trace proves one captured response, not the absence
of later Tushare corrections.

## Availability and bucket authority

```text
available_time = UtcInstant(selected_member.acquired_at_epoch_nanoseconds)
```

It must satisfy `available_time >= bucket.interval_end_exclusive`; otherwise
`AVAILABILITY_INVALID`. The exact later acquisition time is preserved unchanged in the
raw Bar and both projections. It cannot be rewritten as 2024 same-day latency.

The request bucket must bind:

- venue/trading date `CN.XSHE / 2024-01-02`;
- interval start `2024-01-02T01:15:00Z`;
- interval end exclusive `2024-01-02T07:00:00Z`;
- bucket hash `sha256:b58489aeffd996cfa583caac981bfeb39edf0b93280f787d63b0f6b0855dc7b7`.

## Exact projection schemas

### Execution reference

```text
TushareCnAShareDailyExecutionReference@1 = {
  raw_bar_hash: sha256,
  price_purpose: EXECUTION_REFERENCE,
  instrument_id: InstrumentId,
  bucket: BarBucket,
  available_time: UtcInstant,
  open_price: Price,
  high_price: Price,
  low_price: Price,
  close_price: Price,
  volume: Quantity,
  amount: Money,
}
```

Canonical type is `tushare_cn_a_share_daily_execution_reference`; hash is
`canonical_sha256` of the complete type/schema/body. It is historical execution
reference only and does not authorize a same-day fill.

### Valuation

```text
TushareCnAShareDailyValuation@1 = {
  raw_bar_hash: sha256,
  price_purpose: VALUATION,
  instrument_id: InstrumentId,
  valuation_at: bucket.interval_end_exclusive,
  available_time: UtcInstant,
  close_price: Price,
}
```

Canonical type is `tushare_cn_a_share_daily_valuation`; hash is `canonical_sha256` of
the complete type/schema/body. It grants no settlement, adjusted-close, margin,
liquidation, or corporate-action semantics.

`project_execution_reference(raw_bar)` and `project_valuation(raw_bar)` accept only the
exact raw-Bar type. Their hashes and canonical bodies must be distinct.

## Result and outcome

```text
TushareCnAShareDailyNormalizationResult@1 = {
  request: TushareCnAShareDailyNormalizationRequest,
  snapshot: verified SourceSnapshot,
  raw_bar: TushareCnAShareDailyRawBar,
  trace: TushareCnAShareDailySourceTrace,
  execution_reference: TushareCnAShareDailyExecutionReference,
  valuation: TushareCnAShareDailyValuation,
}
```

The result derives `request_hash` from `request` and validates the exact request,
verified snapshot, selected member, provenance/source/revision trace, acquisition
availability, raw Bar, and projection links. Its canonical body contains
`request.to_canonical_dict()` and `snapshot.to_canonical_dict()` metadata only; archive
bytes are never hashed into the result body. Canonical type is
`tushare_cn_a_share_daily_normalization_result`; `normalization_hash` is
`canonical_sha256` of the complete type/schema/body.

`TushareCnAShareDailyNormalizationOutcome` contains exactly one of `result` or
`failure`; it is not a stored artifact.

## Failure contract and precedence

```text
TushareCnAShareDailyNormalizationFailure@1 = {
  code: TushareCnAShareDailyNormalizationFailureCode,
  member_key: str | null,
  field: str | null,
}
```

`failure_hash = canonical_sha256` of exact type/schema/body. Exactly one failure is
returned and no partial Bar, trace, or projection is returned:

1. `INVALID_REQUEST`
2. `SNAPSHOT_INVALID`
3. `SNAPSHOT_BINDING_MISMATCH`
4. `SOURCE_MEMBER_MISSING`
5. `SOURCE_MEMBER_BINDING_MISMATCH`
6. `SOURCE_JSON_INVALID`
7. `SOURCE_SCHEMA_MISMATCH`
8. `SOURCE_RECORD_MISMATCH`
9. `DECIMAL_MAPPING_INVALID`
10. `BAR_INVARIANT_VIOLATION`
11. `BUCKET_BINDING_MISMATCH`
12. `AVAILABILITY_INVALID`

Mixed faults must prove this global order. Acquisition-time/provenance mutation is a
`SNAPSHOT_BINDING_MISMATCH`, before source parsing.

## Implementation seam

Add one internal Builder module
`crypto_quant_bundle_builder.tushare_cn_a_share_daily`, without package-root exports.
Reuse `SourceSnapshot`, `verify_source_snapshot`, `BarBucket`, Domain numeric/time
values, and `canonical_sha256`. Do not add a provider Protocol, factory, registry,
second decimal framework, Runtime import, Trading Kernel import, cache, repository,
path convention, or network access.

## Acceptance evidence required

1. exact snapshot/provenance/member/request binding, including acquisition-time
   mutation with identical bytes;
2. duplicate/malformed JSON, numeric strings, constants, exponent notation, and exact
   schema rejection;
3. raw lexemes retained and exact units/scales reproduced;
4. malformed lexeme, excessive scale, OHLC/change, volume, and amount failures;
5. bucket/session/trading-date binding and actual late availability;
6. exact source-record/raw-Bar/trace/projection/result hash bodies;
7. no `price_purpose` on the raw Bar;
8. mutually distinct execution-reference and valuation projections;
9. no settlement/margin/funding/liquidation/corporate-action/listing claim;
10. mixed-fault precedence and no partial output;
11. no Builder production import of Trading Kernel/Runtime and no root export;
12. existing G12A/B/G fixtures and hashes unchanged.

## Deferred work

- current `stock_basic` remains current metadata only;
- historical listing lifecycle authority;
- provider revision/correction terminal closure;
- corporate-action-adjusted data;
- G12C/D publication and G12I/K/M qualification.
