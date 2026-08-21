---
id: G12K-TUSHARE-FIXED-INSTRUMENT-SOURCE-BOUNDED-V1
readiness: ACCEPTED_SOURCE_BOUNDED_SLICE
gate_status: PASSED
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

D1-D4 `PASSED` at implementation source
`28a4d7234f5101e67bfa64f1eded92b81bfcf73d`. The exact fixed-singleton
Tushare source-bounded slice is accepted; general G12K remains `DRAFT / BLOCKED`.
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

The report also retains `dividend_source_rows`, an ordered canonical replay value.
Each row has exactly 16 entries: provider string/null fields remain string/null;
provider numeric/null fields are represented by their exact validated numeric
lexeme string or null. Field position supplies the type distinction. This value is
not the raw response byte stream, but it is sufficient for nominal reconstruction
to rebuild every `row_bytes`, source-row hash, and relevance decision without
trusting copied hashes or booleans.

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
  supersedes_acquisition_receipt_bytes: bytes | None = None,
  supersedes_snapshot: SourceSnapshot | None = None,
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
   predicate;
7. when a direct predecessor is supplied, requires all three predecessor inputs,
   verifies its receipt/snapshot/archive bytes exactly as current evidence, rebuilds
   its row replay and report while preserving only its already-recorded predecessor
   hash, and compares the rebuilt complete report; and
8. deep-reconstructs the completed report before returning it.

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
dividend_source_rows
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
- `dividend_source_rows` exact-reconstructs every retained row in provider order;
  nominal reconstruction recomputes the complete row-hash tuple and exact relevance
  selection and rejects copied hashes or selections inconsistent with those rows;
  observer raw-evidence replay, predecessor-evidence replay, and the accepted
  canonical-file hash reject row replacement or reordering relative to evidence;
- the first accepted source-row and row-hash tuples each have length 96,
  `has_more=false`, observed count metadata `0`, and an empty target-relevant tuple;
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
nested substitution, constructor bypass, hashes or deterministic relevance output
inconsistent with the retained row replay, or any true qualification flag. Exact
accepted-file and observer evidence comparison reject an otherwise internally
consistent replacement or reordering of the retained rows.

Raw response bytes are not copied into the report. D3 verifies them before report
creation and retains only the exact typed row replay values above. Copied G12I
hashes inside G12K are not sufficient by themselves for Runtime
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
7. `PREDECESSOR_INVALID` — predecessor inputs are partial, malformed,
   constructor-bypassed, receipt/snapshot/archive-inconsistent, or the complete
   predecessor report cannot be rebuilt exactly from its supplied evidence;
8. `CORRECTION_EDGE_INVALID` — a valid predecessor is not the identical fixed
   scope, the new snapshot is unchanged, the new `observed_at` is not later, or
   the direct supersession/report identity is inconsistent;
9. `REPORT_BINDING_MISMATCH` — deterministic row/relevance replay or completed
   report reconstruction disagrees.

Failure data is code plus optional member key only. It contains no raw provider
text, token material, arbitrary exception text, or undeclared filesystem path.

### Append-only direct correction edge

D3 validates one explicitly supplied direct predecessor only. Either all of
`supersedes_report`, `supersedes_acquisition_receipt_bytes`, and
`supersedes_snapshot` are null, or all three are present with exact nominal types.
The predecessor receipt/snapshot/archive is independently verified, its source rows
and relevance are replayed, and a complete expected predecessor report is rebuilt
using only the predecessor's already-recorded `supersedes_report_hash` as an opaque
prior-edge identity. That complete expected report must equal the supplied
predecessor.

The predecessor must be the identical fixed scope; the new snapshot must differ;
new `observed_at` must be later; and the new report sets
`supersedes_report_hash=predecessor.report_hash`. If no predecessor evidence is
supplied, the field is null.

D3 does not validate the predecessor's earlier edge, know repository head state,
detect an omitted intermediate report, or
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

## D2 — bounded acquisition (`PASSED` at `5954b84cbb5bab875cbda2051df876348f30ae12`)

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

## D3 — observation report (`PASSED` at `28a4d7234f5101e67bfa64f1eded92b81bfcf73d`)

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

## D4 — acceptance and nominal G12M handoff (`PASSED`)

The accepted capture is exactly one full Tushare Pro
`dividend(ts_code="000001.SZ")` response for the fixed singleton
`xshe:000001`. It retains 96 rows in provider order, reports `has_more=false` and
observed count metadata `0`, and selects zero rows under the frozen
`[20260706, 20260731)` target-date predicate. The zero selection means only
`NO_TARGET_RELEVANT_ROW_RETURNED_AT_OBSERVED_AS_OF`.

Frozen identities:

- D1 contract source: `3d65a4740c3da6eb923dd5f12a92c0ef8e1e9972`;
- D1 contract amendments: `a274658d47e428a5c5be5a3dedcd79f223ed805d`,
  `060c6e2ce949183e2ad6611eb7bc1da971018e9a`,
  `3addd11376e1974ea577b7ce3604b3b739db0dce`, and
  `ff768d493d9d0d4bc61d280105130d8dab945691`;
- bounded acquisition source: `5954b84cbb5bab875cbda2051df876348f30ae12`;
- observation implementation source: `28a4d7234f5101e67bfa64f1eded92b81bfcf73d`;
- production module file: `sha256:4fe7aea59608fbe7dcf9953b29b97a0bf644e3efe6ef069790c851aa64403546`;
- response file: `sha256:af19248549b55de24f36e120e4c416dd9a23d225c84f96edaa1534cfb377a8af`;
- acquisition receipt file: `sha256:5524257ee9a464d8e72df803c1493bc92e59420f0af1f6593b23a22dbb93a240`;
- SourceSnapshot: `sha256:ecb17991e82a73cc2eaaaa457ff72ccd89cb1a4a23fd595419983028f2c4a5c4`;
- source content tree: `sha256:734b7b3460fda376ee105619fc4f20da33f88a3e5693de50c92389782b872809`;
- provenance: `sha256:475f9a488e7e8c761bd01f55528f1185a1aacbba4868c00190d51a1200c18e0d`;
- request scope: `sha256:5738442bf477fc2f60542fa4b0ddee7be8d737d068077eefaa63d72489935ed7`;
- accepted catalog canonical file: `sha256:d71ca8ed8977bf5fa0aa7cd1ab11fb85abcd5382f42c7e2bb2243d5b5290e456`;
- instrument catalog: `sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc`;
- retained source rows: `sha256:2ed79936a664545591c2f3baf7224c7a632f17416c120eae22022eac56ed07aa`;
- ordered source-row-hash tuple: `sha256:774f8cb53478581c3137c6cc086a76552a0719cfaa121df790c451368b37fb84`;
- empty target-relevant-hash tuple: `sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`;
- report: `sha256:5a49065d87286a9673893337328ddbbab9a19cd3addf178bf96033b9b1babfd7`;
- report canonical file: `sha256:a386f4281374d1449c0b5ba4371b9e9d2de5b236bc8fc5b5cdd8de5e43c65956`.

Acceptance passed 25 focused observer/acquisition/architecture tests, 127 adjacent
Tushare/SourceSnapshot tests, the 192-test architecture suite, and the full
2213-test repository suite. Ruff check/format, primary LSP, compileall, diff checks,
full-repository gitleaks, and independent adversarial review passed. Pyright was not
available in this environment (`ModuleNotFoundError: pyright`); primary LSP was
clean. Accepted G12I/G12CD modules, fixtures, canonical bytes, hashes, APIs, and the
Builder root surface remain unchanged.

G12M is now provider-specific nominally ready for one A-share case only. A future
Runtime slice must independently deep-reconstruct the accepted G12I and G12K
canonical report bytes, bind both accepted canonical-file/report hashes, and
cross-check provider, instrument, scope, G12I dates/Event hashes, and observation
times. Copied G12I hashes inside G12K, caller booleans, naked hashes, generic
`ArtifactRef`, or Runtime→Builder import remain insufficient. Runtime must also
verify the bound run uses exactly singleton `xshe:000001`, has no dynamic universe
selector, and is assessed no earlier than G12K `observed_at`.

General or dynamic-universe G12K remains blocked. Binance observed-as-of evidence is
still required for a Binance nominal case, but does not block this exact
Tushare-only A-share case. No broader listing, universe, survivorship,
corporate-action absence/lifecycle, result-grade, live, legal, or deployment claim
is implied. Corrections require a new snapshot/report and exact predecessor-evidence
replay; prior evidence and Runs remain immutable.
