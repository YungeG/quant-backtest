---
id: G12I-TUSHARE-CN-A-SHARE-DAILY-SOURCE-BOUNDED-V2
readiness: ACCEPTED_SOURCE_BOUNDED_SLICE
gate_status: PASSED
owner: market-bundle-builder Tushare daily coverage
produces:
  - TushareCnAShareDailySourceBoundedObservationReportV2
consumes:
  - ADR 0008
  - exact Tushare daily, trade_cal, and suspend_d raw responses and receipt
  - G12A SourceSnapshot
  - existing Tushare daily normalization, publication, and purpose-scope seams
depends_on:
  contract: [G12A, G12B-TUSHARE-CN-A-SHARE-DAILY-V1, G12CD-TUSHARE-CN-A-SHARE-DAILY-PUBLICATION-V1, G12I-TUSHARE-CN-A-SHARE-DAILY-PURPOSE-SCOPE-V1]
  evidence: [accepted credentialed July-2026 Tushare capture at source 4389877b8879fc9bb1a6d6544c4079a7d29312ab]
fan_out: [G12M-SOURCE-BOUNDED-QUALIFICATION-V1]
---

# G12I Tushare China A-share daily source-bounded v2

## Status and outcome

D1-D4 `PASSED` at implementation source
`4389877b8879fc9bb1a6d6544c4079a7d29312ab`. The exact source-bounded G12I
vertical for one Tushare instrument is accepted. It does not grant result grade,
G12M qualification, live, or deployment authority.

Under [ADR 0008](../../../adr/0008-source-bounded-decision-grade.md), Tushare's lack
of a provider-declared permanent checksum, proof of no future revision, complete
correction lineage, and provider-completeness guarantee is recorded as an explicit
limitation. Those unavailable assurances do not block this source-bounded historical
slice. Missing or inconsistent evidence that Backtest controls remains fail-closed.

Research basis:
[availability/revision authority v2](../../../research/g12i-tushare-availability-revision-authority-v2.md).

## D1 — frozen contract

### Exact scope

- provider/datasets: `tushare.pro` `daily`, `trade_cal`, and `suspend_d` only;
- instrument: `000001.SZ` → `InstrumentId(VenueId("xshe"), "000001")`;
- venue calendar: `XSHE` / provider exchange `SZSE`;
- target: `[2026-07-05T16:00:00Z, 2026-07-30T16:00:00Z)`;
- provider calendar dates: `20260706` through `20260730`, inclusive;
- purposes: `EXECUTION_REFERENCE` and `VALUATION` only;
- stale policy: exact event/bucket, maximum age zero, no forward fill;
- source limitations: permanent provider checksum unavailable, future revision
  finality unknown, correction lineage unavailable, and provider completeness
  unknown.

Tushare and Binance remain the only market-data providers allowed by ADR 0008. This
slice uses Tushare only and adds no provider registry or extension policy.

### Controllable pass conditions

A successful report must bind and verify all of the following for the exact scope:

1. exact raw response bytes for every frozen request, an environment-redacted
   acquisition receipt, per-response receipt time, independently computed local
   SHA-256, and one G12A `SourceSnapshot` identity;
2. exact provider/API/params/fields/member-key binding and unique-key JSON response
   envelopes; `count` is retained as observed metadata and is never interpreted as
   returned-row count or completeness proof;
3. no-lookahead: each normalized daily event retains the receipt time of its exact
   raw response as `available_time`, and no report may move that time backward;
4. every provider date is classified from the captured evidence; an absent open-day
   daily row without full-day suspension authority is blocking;
5. deterministic normalization, one-to-one publication, purpose binding, canonical
   report bytes/hash, and replay parity; and
6. append-only correction handling: a changed response creates a new output
   directory, snapshot, publication, and report and never mutates prior evidence.

The report does not require Tushare to declare terminal correction closure. A
successful report states only what the exact retained responses showed at their
receipt times.

### Conservative daily classification

For each date, require one exact `trade_cal` row before classification:

| Observation | Result |
| --- | --- |
| `is_open=0`, no daily row | `NO_SESSION` |
| `is_open=1`, one exact daily row | publish the observed row |
| `is_open=1`, no daily row, exact full-day `suspend_d` `S` observation with `suspend_timing=null` | `SUSPENDED` |
| `is_open=1`, no daily row, only an intraday suspension interval | fail as unclassified daily absence |
| `is_open=1`, no daily row, no full-day suspension authority | fail as unclassified daily absence |
| daily row on a closed date, duplicate/conflicting rows, or incompatible full-day suspension plus daily row | fail as conflicting evidence |

A returned zero-volume daily row remains an observed row; it is not promoted to
`NO_TRADES`. HTTP, timeout, retry exhaustion, 429, or 5xx evidence is acquisition
failure, not `SOURCE_OUTAGE` authority. This v2 slice never invents `NO_TRADES`,
`MISSING`, or `SOURCE_OUTAGE` classifications.

### Direct-provider-daily seam

G12G aggregation is unnecessary for this slice: each accepted Tushare `daily` row is
already the one daily provider observation published for that trade date. D3 must
reuse the existing Tushare raw-Bar normalizer and v1 MarketEvent projector, extending
their frozen single-date restrictions only as required for the exact July dates and
preserving all accepted 2024 canonical bytes and hashes.

The July bundle uses one unchanged provider-specific stream/capability and one Event
per returned daily row. It must not manufacture an intermediate
`synthetic_price_point.v1`, call `aggregate_bars_v1`, mint a fake
`BarAggregationManifest`, or duplicate the G12G bucket/availability DSL. Existing
`AvailabilityClosureDeclaration` remains unchanged; this provider-specific report
records only direct daily observations and classified absences.

### Sole report and downstream symbols

D3 may add one internal Builder module and only these downstream-consumed symbols:

```text
TushareCnAShareDailySourceBoundedObservationReportV2
TushareCnAShareDailySourceBoundedObservationOutcomeV2
observe_tushare_cn_a_share_daily_source_bounded_v2(...)
```

The outcome contains exactly one report or one structured failure. The report's
canonical body binds:

- fixed provider/datasets/instrument/venue/UTC scope;
- acquisition receipt SHA-256, snapshot/provenance hashes, ordered member keys,
  member content hashes, and per-member receipt times;
- exact MarketBundle ref, manifest/content hash, stream content hash, and ordered
  published Event hashes/dates;
- the two ordered `PricePurposeRequirement` hashes;
- ordered published, `NO_SESSION`, and `SUSPENDED` date sets that exactly partition
  the target dates after successful classification;
- observation time equal to the latest bound response receipt time;
- `supersedes_report_hash`, null for the first capture and otherwise exactly one
  prior report over the same scope;
- fixed source limitations listed above; and
- `decision_grade_eligible=false` and `deployment_authorized=false`.

`report_hash = canonical_sha256(complete body excluding report_hash)`. Raw bytes are
not copied into the report; their verified snapshot/member and receipt identities are
bound. D4 does not directly grant this Builder report to Runtime. After the report
schema, canonical fixture, verifier behavior, and exact accepted hash are frozen, D4
amends the G12M plan to define one nominal Runtime reconstruction boundary for those
exact bytes. That future boundary must deep-reconstruct the complete accepted report
mapping and bind its frozen report/hash identities; a naked hash, caller boolean,
generic `ArtifactRef`, class-name match, or direct Runtime→Builder import is not
accepted.

### Failure precedence

The observation outcome returns no partial report. For mixed faults, first applicable
wins:

1. `INVALID_INPUT`;
2. `EVIDENCE_INVALID` — receipt, snapshot, raw member, local hash, or credential
   redaction verification fails;
3. `REQUEST_SCOPE_MISMATCH`;
4. `RESPONSE_SCHEMA_MISMATCH` — malformed/duplicate-key JSON, envelope, field, row,
   or primitive mismatch;
5. `RESPONSE_PAGE_INCOMPLETE` — an observed response says `has_more=true`; no
   undocumented continuation is inferred;
6. `SOURCE_OBSERVATION_CONFLICT`;
7. `MISSING_CLASSIFICATION` — including missing `trade_cal` authority or any
   unresolved open-day daily absence;
8. `NORMALIZATION_FAILED`;
9. `PUBLICATION_FAILED`;
10. `PURPOSE_SCOPE_MISMATCH`;
11. `LOOKAHEAD_VIOLATION`;
12. `REPORT_BINDING_MISMATCH`.

Failure data is limited to code plus optional provider date/member key. It must not
contain raw provider text, paths outside the declared output, exceptions, or token
material.

## D2 — bounded acquisition

Extend the existing `tools/acquisition` Tushare code only. Reuse
`_post_with_retries`, `_provider_body`, `_stdlib_post`, G12A snapshot freezing, and
the common no-clobber publisher; do not add a second client, transport framework,
credential store, dependency, or provider abstraction.

Frozen requests are:

- one exact `daily` point request for each date `20260706..20260730`, with
  `ts_code=000001.SZ`, `start_date=date`, and `end_date=date`;
- one exact `trade_cal(exchange=SZSE,start_date=20260706,end_date=20260730)` range
  request; and
- one exact `suspend_d(ts_code=000001.SZ,trade_date=date,suspend_type=S)` point
  request for each date `20260706..20260730`.

Request only the fields consumed by the existing daily normalizer, calendar
classification, and full-day suspension classification. Validate unique-key JSON,
exact envelope primitive types, exact requested field order, in-scope row keys, and
no duplicate logical rows. Do not freeze live row counts, assume empty suspension
responses, assign semantics to `count`, or assume `has_more=false` before capture.
The receipt preserves observed `has_more`/`count`; D3 fails closed on a nonterminal
page.

The new no-clobber output directory contains exactly:

```text
response/daily/20260706.json ... response/daily/20260730.json
response/trade-cal/20260706-20260730.json
response/suspend-d/20260706.json ... response/suspend-d/20260730.json
acquisition-receipt.json
```

The receipt is written last and binds every exact request, field list, attempt count,
response receipt time, byte length, local SHA-256, observed envelope metadata, and
one 51-member G12A snapshot. Provider-declared checksums and revision IDs remain
null. Existing output is never replaced; any pre-publication failure removes only
the newly claimed directory.

The sole external barrier is a securely configured environment-only `TUSHARE_TOKEN`
whose account has `daily`, `trade_cal`, and `suspend_d` permissions. The user must
never paste the token into chat, source, receipts, logs, exceptions, tests, fixtures,
or committed artifacts.

D2 write set:

```text
tools/acquisition/cn_a_share_tushare.py
tools/acquisition/cn_a_share_tushare_trade_calendar.py
tests/tools/acquisition/test_cn_a_share_tushare_source_bounded_v2.py
tests/architecture/test_g12i_tushare_source_bounded_boundary.py
```

## D3 — deterministic normalization, publication, and observation

Reuse the existing Tushare daily normalizer, v1 MarketEvent projection, G12C
validation, G12D publication, and `PricePurposeRequirement` values. Extend only their
single-fixture date/member restrictions needed by this exact scope; preserve the
accepted 2024 fixture, signatures, canonical bytes, and hashes.

Build one July Bundle with coverage equal to the target UTC range and events ordered
by provider trade date. Create exactly two July requirements, execution-reference
then valuation, over the same stream/range with zero age and no forward fill. The
new observation module verifies the D2 evidence, classification, Bundle, publication,
purpose hashes, no-lookahead, and replay before returning the sole report.

D3 write set:

```text
packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_daily.py
packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_daily_bundle.py
packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_daily_source_bounded_v2.py
tests/bundle_builder/providers/tushare/test_cn_a_share_daily_source_bounded_v2.py
tests/fixtures/market_data/providers/tushare/cn-a-share-daily-source-bounded-v2/
```

No Builder root export, G12G edit, existing availability declaration edit, Runtime or
Trading Kernel import, network/filesystem access in production, second normalizer,
new publication framework, or generic coverage DSL is allowed.

## D4 — acceptance and G12M binding

Acceptance must prove:

1. exact 51-response request/receipt/snapshot/member/hash binding and token absence;
2. zero/one/many response cases without assumed live counts, empty suspensions, or
   terminal pages;
3. every classification row above, especially unresolved open-day absence blocking;
4. exact reuse and byte compatibility of the accepted 2024 normalizer/publication;
5. execution-reference/valuation separation, zero-age/no-forward-fill, and no
   cross-purpose fallback;
6. receipt-time availability, lookahead rejection, deterministic Event/report bytes,
   idempotent publication/replay, and append-only supersession;
7. exact failure precedence and atomic no-partial output;
8. limitation text without provider finality/completeness claims; and
9. architecture boundaries, Markdown/links, Ruff/Pyright/LSP, focused/full tests,
   import boundaries, diff checks, and gitleaks.

After acceptance, record the exact raw-member hashes, receipt hash, snapshot and
provenance hashes, Bundle/manifest/stream/Event hashes, two requirement hashes,
report canonical-file hash, report hash, and immutable acceptance commit. Amend
G12M only to bind those exact accepted identities. Do not update G12M from planned
names or unhashed live captures.

Future D4 documentation write set is limited to this plan, `g12i.md`, this G12
README, `g12m-source-bounded-qualification-v1.md`, and the Acceptance Matrix. The
G12M edit may freeze only the exact nominal reconstruction boundary after accepted
report bytes/hashes exist; it may not add a generic mapping/provider framework. D1
does not edit the Acceptance Matrix.

## D4 acceptance closure

The accepted capture contains 51 ordered provider responses plus one receipt: 25
`daily` point responses, one `trade_cal` range response, and 25 `suspend_d` point
responses. It classifies 19 published sessions, six `NO_SESSION` dates, and zero
full-day suspensions. The retained fixture directory has 54 files after adding the
canonical observation and publication expectations.

Frozen identities:

- implementation source: `4389877b8879fc9bb1a6d6544c4079a7d29312ab`;
- acquisition receipt file: `sha256:95ba0d8e28414aa997e232c90eee03318f13f2c9041b36f4da046bbc5b2fb623`;
- SourceSnapshot: `sha256:9f1915e302e1a1f5b74a2cdccb54c08676642da3b48642eb9bbf728dc4c98f2e`;
- source content tree: `sha256:ef44ecd44476dcd3d1cd69f82305df29d186c82350c45f427b5bf008b62d57af`;
- provenance: `sha256:4dba800ca4688504c804009bcb21a4698cc431761be6847a81bfeef02a0e05e4`;
- Bundle manifest body: `sha256:87e1209b5510e9d5489d414e63c1008117282a57e1d05555113103222f06a505`;
- Bundle ref manifest: `sha256:d9f73a48eeb8b92600cd7fdd9017ba8b0536654cb466ce57c8bc6695f10271df`;
- stream: `sha256:da735d4545e458f8bb1432008b89e45b7c820812f0fed91ebc6610721ad491a1`;
- execution-reference requirement: `sha256:9a4d38330cc1048cc5c7181d67614585e0d47f63f6a51e8ce8ed66b5488bbfcb`;
- valuation requirement: `sha256:14a2f05bcaf6edc8540fd3ce1e850a04af5fb0e5a8405154ba1ab41d4faf5a6d`;
- report: `sha256:ff09c4ad9f8025e66689387b5132d3d85c4101276fbf7330dd5040af111cc029`;
- report canonical file: `sha256:9cbfc115e41f56d1e83eac520856c3f529f83972b97111238e5dbb1a68c4eae6`;
- publication expectation: `sha256:2cdb6a121262946b726b5b7553c622d458a0079b226db6afc954b17ec43c4f69`.

Acceptance passed 92 focused/compatibility tests, 284 Builder/adjacent architecture
tests, and the full 2188-test repository suite. Import boundaries passed for 126
files; Ruff, Pyright, primary/auxiliary LSP, lock, diff, full-repository gitleaks,
token-absence checks, and independent review passed. Existing v1 normalizer,
projector, Builder root, signatures, fixtures, and protected source hashes remain
byte-identical. The accepted off-root v2 module is exact-scope because the frozen v1
values hard-code the 2024 member/date/amount contract; it reuses their low-level
JSON, numeric, source-record, Snapshot, Event payload, G12C validation, G12D
publication, and purpose semantics without changing v1 bytes or adding a generic
provider framework.

All qualification flags remain false. Corrections require a new snapshot/report
whose `supersedes_report_hash` binds the prior accepted report; no existing evidence
or Run is overwritten.

## Non-goals

No provider terminal closure, permanent checksum, provider-complete scope, correction
ledger, `NO_TRADES`/`SOURCE_OUTAGE` invention, generic availability/revision DSL,
G12G aggregation, second Tushare client, adjusted/settlement/liquidation price,
historical listing/corporate-action qualification, provider registry, G12M result
qualification, decision-grade claim, live decision, deployment authorization,
commit, push, staging, or live acquisition in D1.
