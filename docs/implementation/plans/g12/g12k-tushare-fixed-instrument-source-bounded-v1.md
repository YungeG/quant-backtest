---
id: G12K-TUSHARE-FIXED-INSTRUMENT-SOURCE-BOUNDED-V1
readiness: BLOCKED
contract_status: D1_PASSED
implementation_status: UNIMPLEMENTED
owner: market-bundle-builder G12K fixed-instrument observation
produces:
  - G12KFixedInstrumentSourceBoundedObservationReportV1
consumes:
  - ADR 0008
  - accepted G12I Tushare daily source-bounded v2 canonical report
  - accepted G12CD Tushare catalog-bound publication v2 catalog artifact
  - exact Tushare Pro dividend response and acquisition receipt
  - G12A SourceSnapshot
  - environment-only TUSHARE_TOKEN
depends_on:
  contract: [G12A, G12CD-TUSHARE-CN-A-SHARE-DAILY-PUBLICATION-V2, G12I-TUSHARE-CN-A-SHARE-DAILY-SOURCE-BOUNDED-V2, G12K]
  evidence:
    - accepted G12I source 4389877b8879fc9bb1a6d6544c4079a7d29312ab
    - accepted G12CD catalog source 590901802915df79d69d9bd85f00bb6c3290f5a3
  write_conflict: [provider-observation-policy, acceptance-registry]
fan_out: [G12M-SOURCE-BOUNDED-QUALIFICATION-V1]
---

# G12K Tushare fixed-instrument source-bounded v1

## Status and purpose

D1 is frozen and passed. General G12K remains `DRAFT / BLOCKED`.
The slice is deliberately narrower than listing/universe qualification: it records
positive Tushare daily-row presence for one preselected instrument and the exact
corporate-action rows returned by one observed-as-of Tushare response. It does not
establish historical listing status, membership continuity, a point-in-time market
universe, survivorship safety, action lifecycle closure, or provider finality.

The nominal downstream use is restricted to a future G12M A-share case whose run
universe is already fixed to singleton `xshe:000001` and has no dynamic universe
selector. The report is upstream evidence only; all grade, profile, live, and
deployment flags remain false.

## D1 — frozen contract

### Exact fixed scope

- provider: `tushare.pro`;
- new dataset: `dividend` only;
- provider code / domain instrument: `000001.SZ` /
  `InstrumentId(VenueId("xshe"), "000001")`;
- venue calendar / provider exchange: `XSHE` / `SZSE`;
- UTC interval: `[2026-07-05T16:00:00Z, 2026-07-30T16:00:00Z)`;
- provider-date interval: `[20260706, 20260731)`;
- no dynamic selector, no market-wide universe, and no instrument substitution.

### Accepted G12CD catalog identity

The fixed instrument/type/currency value comes from accepted G12CD catalog-bound
publication v2, not from the July G12I publication. G12I v2 deliberately binds a
zero catalog hash and supplies no catalog authority.

D3 receives one exact `InstrumentCatalog` value and deep-reconstructs this body:

```text
InstrumentCatalog(
  currencies=(CurrencyId("CNY"),),
  instruments=(
    InstrumentDefinition(
      instrument_id=InstrumentId(VenueId("xshe"), "000001"),
      instrument_type=InstrumentType.EQUITY,
      base_currency=None,
      quote_currency=CurrencyId("CNY"),
      settlement_currency=CurrencyId("CNY"),
    ),
  ),
  symbol_timelines=(),
)
```

It must bind:

- G12CD source `590901802915df79d69d9bd85f00bb6c3290f5a3`;
- accepted canonical fixture file
  `sha256:d71ca8ed8977bf5fa0aa7cd1ab11fb85abcd5382f42c7e2bb2243d5b5290e456`;
- publication
  `sha256:d6bada1c3a9aef99ddaab718e77e2f9329b1da5821a9136f62585d2e3bb1c59b`;
- catalog source
  `sha256:59d3267cbf79d4721357d5959f3e848d7a3c250802fe055b4cd40e0aa0a0b8f5`;
- instrument catalog
  `sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc`.

This catalog is used only for fixed instrument/type/CNY identity. Its source is
current metadata and grants no historical listing, membership, timeline, or
survivorship authority.

### Accepted G12I presence anchor

D3 receives exact canonical-file bytes for accepted G12I type
`tushare_cn_a_share_daily_source_bounded_observation_report`, schema version `2`.
It parses bytes with a duplicate-key/invalid-constant rejecting JSON parser,
deep-reconstructs the exact nominal report, and requires:

```text
canonical_bytes(reconstructed.to_canonical_dict()) + b"\n" == supplied_bytes
```

It then binds all fixed G12I scope and identities, including:

- source `4389877b8879fc9bb1a6d6544c4079a7d29312ab`;
- canonical report file
  `sha256:9cbfc115e41f56d1e83eac520856c3f529f83972b97111238e5dbb1a68c4eae6`;
- report
  `sha256:ff09c4ad9f8025e66689387b5132d3d85c4101276fbf7330dd5040af111cc029`;
- receipt
  `sha256:95ba0d8e28414aa997e232c90eee03318f13f2c9041b36f4da046bbc5b2fb623`;
- snapshot
  `sha256:9f1915e302e1a1f5b74a2cdccb54c08676642da3b48642eb9bbf728dc4c98f2e`;
- snapshot content tree
  `sha256:ef44ecd44476dcd3d1cd69f82305df29d186c82350c45f427b5bf008b62d57af`;
- provenance
  `sha256:4dba800ca4688504c804009bcb21a4698cc431761be6847a81bfeef02a0e05e4`;
- manifest body
  `sha256:87e1209b5510e9d5489d414e63c1008117282a57e1d05555113103222f06a505`;
- Bundle-ref manifest
  `sha256:d9f73a48eeb8b92600cd7fdd9017ba8b0536654cb466ce57c8bc6695f10271df`;
- stream
  `sha256:da735d4545e458f8bb1432008b89e45b7c820812f0fed91ebc6610721ad491a1`;
- exactly 19 ordered published provider dates and Event hashes, six ordered
  `NO_SESSION` dates, and zero suspended dates.

The only membership-like statement permitted is
`OBSERVED_DAILY_ROW_AT_SESSION`: Tushare returned one exact daily row for
`000001.SZ` on each of the 19 accepted open sessions. This statement must not be
named or projected as `listing_membership`, listing authority, continuity, or
survivorship evidence.

### Exact request-scope identity

The exact ordered field tuple is:

```text
(
  "ts_code", "end_date", "ann_date", "div_proc", "stk_div",
  "stk_bo_rate", "stk_co_rate", "cash_div", "cash_div_tax",
  "record_date", "ex_date", "pay_date", "div_listdate",
  "imp_ann_date", "base_date", "base_share",
)
```

The exact canonical preimage for `acquisition_request_scope_hash` is:

```text
{
  "type": "g12k_fixed_instrument_acquisition_request_scope",
  "schema_version": 1,
  "provider_key": "tushare.pro",
  "api_name": "dividend",
  "params": {"ts_code": "000001.SZ"},
  "fields": <exact ordered field tuple>,
  "member_key": "response/dividend.json",
  "instrument_id": InstrumentId(VenueId("xshe"), "000001"),
  "instrument_catalog_hash": "sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc",
  "venue_calendar": "XSHE",
  "provider_exchange": "SZSE",
  "coverage_start": UtcInstant(1783267200000000000),
  "coverage_end_exclusive": UtcInstant(1785427200000000000),
}
```

Its frozen hash is
`sha256:5738442bf477fc2f60542fa4b0ddee7be8d737d068077eefaa63d72489935ed7`.
No alternate field order, member key, date scope, catalog, provider, or params map
has the same request identity.

### Exact acquisition request and receipt

D2 performs exactly one provider request, with no date or limit parameter:

```text
dividend(ts_code="000001.SZ", fields=<exact ordered field tuple>)
```

The no-clobber output contains exactly:

```text
response/dividend.json
acquisition-receipt.json
```

The canonical request body is exact:

```text
{
  "type": "tushare_g12k_fixed_instrument_source_bounded_request",
  "schema_version": 1,
  "ts_code": "000001.SZ",
  "coverage_start_date": "20260706",
  "coverage_end_date_exclusive": "20260731",
}
```

The exact receipt mapping is:

```text
{
  "type": "tushare_g12k_fixed_instrument_source_bounded_acquisition_receipt",
  "schema_version": 1,
  "request": <exact request body>,
  "request_scope_hash": <frozen request-scope hash>,
  "provider_requests": [
    {
      "api_name": "dividend",
      "params": {"ts_code": "000001.SZ"},
      "fields": <comma-joined exact ordered field tuple>,
      "member_key": "response/dividend.json",
      "attempts": <positive int>,
      "response_received_at_epoch_nanoseconds": <nonnegative int>,
      "response_byte_count": <nonnegative int>,
      "response_sha256": <local sha256>,
      "returned_row_count": <nonnegative int>,
      "observed_envelope": {"has_more": <exact bool>, "count": <exact int>},
      "declared_sha256": null,
      "provider_revision_id": null,
    }
  ],
  "acquired_at_epoch_nanoseconds": <same response receipt time>,
  "snapshot": <exact one-member SourceSnapshot canonical mapping>,
  "provider_declared_sha256": null,
  "provider_revision_id": null,
  "decision_grade_eligible": false,
  "deployment_authorized": false,
}
```

The one-member snapshot uses:

```text
member_key = "response/dividend.json"
provenance.vendor_key = "tushare.pro"
provenance.source_key =
  "tushare.pro.g12k.fixed_instrument_dividend.000001.sz.20260706.20260730"
provenance.license_ref = "tushare.pro.terms"
provenance.retention_policy_ref = "backtest.acquisition.candidate"
decision_grade_eligible = false
deployment_authorized = false
```

`response_byte_count`, response/member hashes, member receipt time, and snapshot
member metadata must exact-match retained bytes. Receipt bytes use the repository
`json_bytes` form: duplicate-free canonical JSON plus exactly one trailing LF.

The first accepted response is expected to contain 96 ordered rows,
`has_more=false`, and observed `count=0`. `count` is retained metadata and is not
interpreted as row count or completeness. D2 validates unique-key JSON, exact
envelope/field order, exact row shape, `ts_code="000001.SZ"`, canonical-or-null
date fields, finite-or-null numeric fields, and credential absence. It preserves
response order and every row. Duplicate or similar economic rows are not collapsed
and no dedup winner is inferred.

### Frozen target-relevance predicate

Domain `canonical_sha256` rejects floats, while Tushare rows contain JSON numbers.
D3 therefore preserves every valid JSON numeric token's exact ASCII lexeme rather
than converting it to Python `float`. For each retained row, define:

```text
fields_bytes = compact UTF-8 JSON array of the exact ordered field names
row_bytes = compact UTF-8 JSON array where:
  null   -> b"null"
  string -> standard ensure_ascii=false JSON string bytes
  number -> the exact validated provider JSON numeric-token bytes
source_row_hash = sha256(
  b'{"fields":' + fields_bytes + b',"row":' + row_bytes + b'}'
)
```

The numeric token grammar is exact finite JSON number syntax; `NaN`, infinities,
invalid constants, malformed exponents, and non-finite conversions fail. This
explicit D1 clarification replaces the impossible float-bearing
`canonical_sha256({...})` shorthand; it does not change the request-scope hash,
report canonicalization, field order, source order, or accepted response bytes.

A row is target-relevant iff at least one non-null value in this exact ordered
field tuple is within provider-date interval `[20260706, 20260731)`:

```text
("ann_date", "record_date", "ex_date", "pay_date", "div_listdate", "imp_ann_date")
```

Each source row is selected at most once even if several fields match. Selected
hashes retain provider response order. The first accepted capture is expected to
bind 96 ordered source-row hashes and an empty target-relevant tuple. Empty means
only `NO_TARGET_RELEVANT_ROW_RETURNED_AT_OBSERVED_AS_OF`; it is not action absence,
completeness, terminality, cancellation, or revision closure.

### Exact observer and nominal report

D3 may add only these provider-specific symbols:

```text
G12KFixedInstrumentSourceBoundedObservationReportV1
G12KFixedInstrumentSourceBoundedObservationOutcomeV1
observe_g12k_tushare_fixed_instrument_source_bounded_v1(
  *,
  g12i_report_bytes: bytes,
  acquisition_receipt_bytes: bytes,
  snapshot: SourceSnapshot,
  instrument_catalog: InstrumentCatalog,
  supersedes_report: G12KFixedInstrumentSourceBoundedObservationReportV1 | None = None,
) -> G12KFixedInstrumentSourceBoundedObservationOutcomeV1
```

The observer:

1. requires exact input types;
2. parses G12I and receipt bytes with duplicate-key and invalid-constant rejection;
3. deep-reconstructs both nominal mappings and requires
   `canonical_bytes(reconstructed) + b"\n" == supplied_bytes`;
4. verifies the exact `SourceSnapshot`, archive member, receipt/member/hash/time
   bindings, and credential absence;
5. deep-reconstructs the exact supplied `InstrumentCatalog` and binds accepted
   G12CD identities;
6. deterministically hashes every source row and applies the frozen relevance
   predicate; and
7. deep-reconstructs the completed report before returning it.

The report canonical body has these fields in this order, followed by computed
`report_hash`:

```text
provider_key
datasets
instrument_id
catalog_artifact_canonical_file_sha256
catalog_publication_hash
catalog_source_hash
instrument_catalog_hash
venue_calendar
provider_exchange
coverage_start
coverage_end_exclusive
g12i_report_canonical_file_sha256
g12i_report_hash
g12i_snapshot_id
g12i_manifest_content_hash
g12i_bundle_ref_manifest_hash
g12i_stream_content_hash
observed_daily_provider_dates
observed_daily_event_hashes
no_session_provider_dates
suspended_provider_dates
acquisition_request_scope_hash
acquisition_receipt_sha256
snapshot_id
snapshot_content_tree_hash
provenance_hash
member_keys
member_content_hashes
member_acquired_at_epoch_nanoseconds
dividend_response_has_more
dividend_response_count_metadata
dividend_source_row_hashes
target_relevance_fields
target_relevant_row_hashes
observed_at
supersedes_report_hash
limitations
availability_closure_complete
revision_closure_complete
provider_authority_qualified
provider_revision_completeness_qualified
historical_listing_status_qualified
listing_membership_continuity_qualified
whole_universe_complete
survivorship_bias_safe
corporate_action_lifecycle_qualified
decision_grade_eligible
profile_qualified
live_eligible
deployment_authorized
```

Fixed invariants:

- type is `g12k_fixed_instrument_source_bounded_observation_report`, schema `1`;
- `provider_key="tushare.pro"`, `datasets=("dividend",)`, and all scope/catalog
  identities exact-match this contract;
- G12I dates/Event hashes are copied only after deep reconstruction of the exact
  accepted G12I canonical-file bytes;
- `member_keys=("response/dividend.json",)` and the member hash/time bind receipt,
  snapshot, and raw archive bytes;
- request-scope hash is the exact frozen value above;
- the first accepted row-hash tuple has length 96, `has_more=false`, observed
  count metadata `0`, and an empty target-relevant tuple;
- `observed_at` is the later of accepted G12I `observed_at` and the dividend member
  receipt time; it is never moved backward;
- `supersedes_report_hash` is null when no predecessor is supplied; and
- every boolean field is exact `bool` and false.

The exact limitations tuple is:

```text
(
  "permanent_provider_checksum_unavailable",
  "future_revision_finality_unknown",
  "provider_correction_lineage_unavailable",
  "provider_completeness_unknown",
  "g12i_daily_presence_is_not_listing_membership",
  "historical_listing_authority_unavailable",
  "listing_membership_continuity_unavailable",
  "whole_universe_completeness_unavailable",
  "survivorship_safety_unavailable",
  "corporate_action_lifecycle_closure_unavailable",
  "zero_target_dividend_rows_is_not_absence_authority",
  "bak_basic_unavailable_to_observed_credential_code_40203",
)
```

The provider correction-lineage limitation is distinct from Backtest's local
`supersedes_report_hash` edge.

`report_hash = canonical_sha256(complete body excluding report_hash)`. Exact
`from_canonical_dict()` reconstruction rejects unknown/missing keys, coercion,
nested substitution, constructor bypass, changed hashes, changed row order,
changed deterministic relevance output, or any true qualification flag.

Raw bytes are not copied into the report. D3 verifies them before report creation.
Copied G12I hashes inside G12K are not sufficient by themselves for Runtime
qualification; the future G12M boundary independently consumes both canonical
reports.

### Failure precedence

The outcome contains exactly one report or one failure and never partial output.
First applicable trigger wins:

1. `INVALID_INPUT` — a supplied argument has the wrong exact type;
2. `EVIDENCE_INVALID` — G12I/receipt bytes are malformed, duplicate-key,
   noncanonical, or nominally unreconstructable; snapshot verification, archive
   extraction, byte/hash/time binding, or credential-redaction verification fails;
3. `REQUEST_SCOPE_MISMATCH` — a valid canonical receipt/request/provider-request,
   snapshot provenance, or request-scope preimage does not match the frozen scope;
4. `RESPONSE_SCHEMA_MISMATCH` — retained response bytes have an invalid envelope,
   field order, row shape, primitive, instrument, or date value;
5. `RESPONSE_PAGE_INCOMPLETE` — retained response says `has_more=true`;
6. `SOURCE_REFERENCE_MISMATCH` — valid canonical G12I bytes or a valid exact
   catalog value do not match the accepted G12I/G12CD identities;
7. `PREDECESSOR_INVALID` — an exact-type predecessor fails deep canonical
   reconstruction, including constructor-bypass detection;
8. `CORRECTION_EDGE_INVALID` — a valid predecessor is not the identical fixed
   scope, the new snapshot is unchanged, the new `observed_at` is not later, or
   the direct supersession/report identity is inconsistent;
9. `REPORT_BINDING_MISMATCH` — deterministic row/relevance replay or completed
   report reconstruction disagrees.

Failure data is code plus optional member key only. It contains no raw provider
text, token material, arbitrary exception text, or undeclared filesystem path.

### Append-only direct correction edge

D3 validates one explicitly supplied direct predecessor only. The predecessor must
be the identical fixed scope; the new snapshot must differ; new `observed_at` must
be later; and the new report sets
`supersedes_report_hash=predecessor.report_hash`. If no predecessor is supplied,
the field is null.

D3 does not know repository head state, detect an omitted intermediate report, or
reject competing successors. Acceptance/repository/consumer policy establishes
currentness and rejects forks. Prior bytes, reports, runs, and results remain
immutable. Local direct supersession does not manufacture provider correction
lineage.

### Architecture and nonclaims

- Production D3 has no network or filesystem I/O.
- Builder does not import Runtime or Kernel; Runtime does not import Builder.
- No root export, provider registry, generic source framework, facts registry,
  cache, repository, policy DSL, or alternate catalog is added.
- Do not modify accepted G12I or G12CD modules, fixtures, canonical bytes, hashes,
  or APIs.
- Do not invoke the synthetic G12K analyzer or construct terminal
  `UniverseCoverageReport`, `CorporateActionCoverageReport`, listing-membership
  Events, corporate-action lifecycle Events, or explicit-empty closure.
- `stock_basic` is not July historical-as-of authority. `bak_basic` is not a
  production request; the observed credential-scoped `code 40203` rejection is a
  limitation only and is never serialized with secret material.
- No result grade, profile qualification, legal/compliance claim, live eligibility,
  or deployment authorization is granted.

## D2 — bounded acquisition (unimplemented)

Authorized write set:

```text
tools/acquisition/cn_a_share_tushare_g12k_fixed_instrument.py
tests/tools/acquisition/test_cn_a_share_tushare_g12k_fixed_instrument.py
tests/architecture/test_g12k_tushare_fixed_instrument_boundary.py
tests/fixtures/market_data/providers/tushare/g12k-fixed-instrument-source-bounded-v1/response/dividend.json
tests/fixtures/market_data/providers/tushare/g12k-fixed-instrument-source-bounded-v1/acquisition-receipt.json
```

D2 exits only after focused acquisition tests, no-clobber/atomic-publication tests,
malformed/duplicate-key/credential tests, exact response capture, and secret scans
pass. D2 does not modify accepted acquisition modules used by G12I or the older
Tushare authority fixture.

## D3 — observation report (unimplemented)

Authorized write set:

```text
packages/market-bundle-builder/src/crypto_quant_bundle_builder/g12k_tushare_fixed_instrument_source_bounded_v1.py
tests/bundle_builder/providers/tushare/test_g12k_tushare_fixed_instrument_source_bounded_v1.py
tests/architecture/test_g12k_tushare_fixed_instrument_boundary.py
tests/fixtures/market_data/providers/tushare/g12k-fixed-instrument-source-bounded-v1/observation-report.expected.json
```

D3 exits only after exact G12I/catalog reconstruction, raw receipt/snapshot/member
verification, deterministic row/relevance hashing, canonical report replay,
append-only direct-edge tests, failure-precedence tests, architecture tests, and
preservation of accepted production bytes pass.

## D4 — acceptance and nominal G12M handoff (unimplemented)

Authorized documentation write set:

```text
docs/implementation/plans/g12/g12k-tushare-fixed-instrument-source-bounded-v1.md
docs/implementation/plans/g12/README.md
docs/implementation/plans/g12/g12k.md
docs/implementation/plans/g12/g12m-source-bounded-qualification-v1.md
docs/implementation/acceptance-matrix.md
```

D4 records exact fixture/report/file/snapshot/request/source-row hashes and the
immutable implementation commit. It formally amends G12M into provider-specific
nominal readiness:

- the A-share fixed-singleton case independently consumes and nominally
  deep-reconstructs both accepted G12I and G12K canonical report bytes, binds both
  accepted canonical-file/report hashes, and cross-checks provider, instrument,
  scope, dates/Event hashes, and observation times;
- copied G12I hashes inside G12K, caller booleans, naked hashes, generic
  `ArtifactRef`, or Runtime→Builder import are insufficient;
- Runtime separately verifies the bound run uses exactly singleton `xshe:000001`,
  has no dynamic universe selector, and the assessment instant is not earlier than
  G12K `observed_at`;
- general/dynamic-universe G12K remains blocked; and
- Binance evidence remains required for a Binance nominal case, but does not block
  this exact Tushare-only A-share nominal case.

No broader listing, universe, survivorship, corporate-action, result-grade, live,
legal, or deployment claim is implied.
