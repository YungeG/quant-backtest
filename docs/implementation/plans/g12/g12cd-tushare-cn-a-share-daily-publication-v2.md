---
id: G12CD-TUSHARE-CN-A-SHARE-DAILY-PUBLICATION-V2
readiness: READY
gate_status: READY
owner: market-bundle-builder internal Tushare catalog-bound daily publication
produces:
  - one acquisition-time current-metadata InstrumentCatalog for 000001.SZ
  - one catalog-bound development-only MarketEvent v2
consumes:
  - G12B-TUSHARE-CN-A-SHARE-DAILY-V1 normalization result
  - the stock_basic member in the same accepted G12A SourceSnapshot
  - unchanged G12C validation and G12D local publication seams
depends_on:
  contract: [G12B-TUSHARE-CN-A-SHARE-DAILY-V1, G12CD-TUSHARE-CN-A-SHARE-DAILY-PUBLICATION-V1, G12C, G12D, G10A]
  evidence: [g12l-tushare-cn-a-share-daily-listing-v1]
fan_out: [G12K]
---

# G12C/D Tushare China A-share Catalog-bound Daily Publication v2

## Status

`READY`. This plan freezes one additive test-first slice. Production and RED tests
are not implemented by this plan commit. The accepted v1 normalizer, v1 projection,
fixtures, hashes, signatures, G12C/D seams, package roots, and shared plan registries
remain unchanged.

This slice narrows one G12K prerequisite by binding a real canonical catalog body
and hash to a new manifest. It does **not** make G12K ready: the Domain catalog has
no provider-source fields, no listing/membership revisions or closure declarations
are added, and the source is current metadata observed only at acquisition time.

## Outcome and boundary

For the existing exact `000001.SZ / 2024-01-02` accepted normalization result:

1. read only `response/stock-basic.json` from that result's already verified G12A
   snapshot;
2. parse the exact one-row current `stock_basic` response;
3. construct one existing Domain `InstrumentCatalog` for `xshe:000001`;
4. retain acquisition/source metadata in a Builder-local canonical source value;
5. project a distinct v2 Event that embeds the exact catalog body, catalog hash,
   source value, and the five accepted v1 economic/source payload components;
6. pass that one Event unchanged through existing G12C and G12D with
   `manifest.instrument_catalog_hash == canonical_sha256(instrument_catalog)`.

The source row's `list_status`, `list_date`, and `delist_date` are retained only as
current metadata returned at acquisition time. They are not evaluated against the
2024 Bar date, do not create a `SymbolTimeline`, and grant no listing interval,
historical listing, membership, survivorship, provider revision closure, corporate
action, decision-grade, live, or deployment authority.

## Placement and single internal seam

Add one production module only:

```text
crypto_quant_bundle_builder.tushare_cn_a_share_daily_catalog_bundle
```

Its only orchestration function is:

```text
project_tushare_cn_a_share_daily_catalog_bound_market_event_v2(
  result: TushareCnAShareDailyNormalizationResult,
) -> TushareCnAShareDailyCatalogPublicationOutcome
```

The module may define only the fixed value/failure/result types and private helpers
needed by that function. It must reuse:

- `TushareCnAShareDailyNormalizationResult`;
- `project_tushare_cn_a_share_daily_market_event_v1` as the accepted v1 projection
  authority;
- `SourceSnapshot.member_bytes()` and accepted snapshot reconstruction;
- existing Domain `CurrencyId`, `InstrumentId`, `InstrumentDefinition`,
  `InstrumentType`, and `InstrumentCatalog`;
- existing `MarketEvent`, `MarketBundleCapability`, `canonical_bytes`, and
  `canonical_sha256`.

No existing production module is edited. In particular, do not edit:

- `tushare_cn_a_share_daily.py`;
- `tushare_cn_a_share_daily_bundle.py`;
- Builder `__init__.py`;
- G12C validation or G12D repository code;
- Domain instrument contracts or Market Data manifest contracts.

There is no Builder root export. Do not add a Protocol, adapter, parser framework,
factory, registry, repository wrapper, catalog store, Reader, cache, callback,
network path, Runtime import, or Trading Kernel import.

## Exact stock-basic grammar

Decode bytes as strict UTF-8 and parse with stdlib `json` using duplicate-object-key
rejection and non-finite constant rejection. No generic parser abstraction is added.

The response wrapper is exact:

```text
top-level keys = ("request_id", "code", "data", "msg", "detail")
request_id = non-empty canonical NFC JSON string
code = exact integer 0
msg = exact empty string
detail = JSON string

data keys = ("fields", "items", "has_more", "count")
has_more = exact false
count = exact integer 0
fields = (
  "ts_code", "symbol", "name", "area", "industry", "market",
  "exchange", "list_status", "list_date", "delist_date",
)
items = exactly one row
```

Every non-null row value is a canonical NFC JSON string; `delist_date` alone may be
null. Extra/missing keys, wrong primitive types, duplicate keys, malformed UTF-8 or
JSON, nonzero code, nonempty message, pagination, count mismatch, field mismatch,
or row-count mismatch fail atomically.

The only accepted v2 row is the immutable captured current-metadata row:

```text
("000001.SZ", "000001", "平安银行", "深圳", "银行", "主板",
 "SZSE", "L", "19910403", null)
```

This exact-row restriction is deliberate single-fixture scope, not a generic
Tushare identifier/listing mapper.

## Exact catalog

Reuse the existing Domain `InstrumentCatalog`; do not create a second catalog
schema. The exact body is:

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

The exact canonical body is:

```json
{"currencies":[{"type":"currency_id","value":"CNY"}],"instruments":[{"base_currency":null,"instrument_id":{"stable_key":"000001","type":"instrument_id","venue":"xshe"},"instrument_type":"equity","quote_currency":{"type":"currency_id","value":"CNY"},"settlement_currency":{"type":"currency_id","value":"CNY"},"type":"instrument_definition"}],"symbol_timelines":[],"type":"instrument_catalog"}
```

```text
instrument_catalog_hash =
sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc
```

`InstrumentType.EQUITY` and CNY quote/settlement are frozen only for this exact
accepted row and the already accepted CNY daily result. `base_currency=None` follows
the existing broad equity contract. `symbol_timelines=()` is mandatory because the
current `stock_basic` response is not historical symbol authority. No name, area,
industry, board, status, or date is inserted into `InstrumentDefinition`.

## Catalog source value

Add one frozen/slotted Builder-local value:

```text
TushareCnAShareAcquisitionCatalogSource@1 = {
  snapshot_id: sha256,
  provenance_hash: sha256,
  source_key: "tushare.pro.daily_listing.000001.sz.20240102",
  member_key: "response/stock-basic.json",
  member_content_hash: sha256,
  record_index: 0,
  acquired_at: UtcInstant,
  provider_ts_code: "000001.SZ",
  provider_symbol: "000001",
  provider_name: "平安银行",
  provider_area: "深圳",
  provider_industry: "银行",
  provider_market: "主板",
  provider_exchange: "SZSE",
  provider_list_status: "L",
  provider_list_date: "19910403",
  provider_delist_date: null,
  source_record_hash: sha256,
  instrument_catalog_hash: sha256,
  current_metadata_only: true,
  provider_revision_id: null,
  revision_closure_complete: false,
  historical_listing_status_qualified: false,
  survivorship_bias_safe: false,
  decision_grade_eligible: false,
  deployment_authorized: false,
}
```

The constructor rebuilds all nested values, requires exact primitive types, requires
`acquired_at == result.raw_bar.available_time`, and recomputes both hashes. It must
reject `bool` masquerading as integer and constructor-bypass forgeries.

```text
source_record_hash = canonical_sha256({
  type: "tushare_cn_a_share_acquisition_catalog_source_record",
  schema_version: 1,
  fields: exact ten-field tuple,
  values: exact ten-value tuple,
})
```

```text
source_record_hash =
sha256:851faa23c64268676dccdb7365b058362aae6ca3a2613752466e460bd7bb1b1e
```

`catalog_source_hash` is `canonical_sha256` of the complete
`tushare_cn_a_share_acquisition_catalog_source` body above, excluding only
`catalog_source_hash` itself:

```text
catalog_source_hash =
sha256:59d3267cbf79d4721357d5959f3e848d7a3c250802fe055b4cd40e0aa0a0b8f5
```

The value is source binding, not a listing revision, membership declaration,
provider checksum, correction record, or closure proof.

## Result, outcome, and binding identity

Add:

```text
TushareCnAShareDailyCatalogPublicationResult@1 = {
  normalization_result: TushareCnAShareDailyNormalizationResult,
  instrument_catalog: InstrumentCatalog,
  catalog_source: TushareCnAShareAcquisitionCatalogSource,
  market_event: MarketEvent,
}

TushareCnAShareDailyCatalogPublicationOutcome = exactly one of {
  result,
  failure,
}
```

The result constructor reconstructs the accepted normalization authority, catalog,
source value, v1 projection, and v2 Event. Its canonical body contains only the
normalization hash plus the complete catalog, catalog hash, catalog source, binding
hash, and v2 Event; raw snapshot archive bytes are never copied.

```text
catalog_binding_hash = canonical_sha256({
  type: "tushare_cn_a_share_daily_catalog_binding",
  schema_version: 1,
  normalization_hash,
  instrument_catalog_hash,
  catalog_source_hash,
})
```

```text
catalog_binding_hash =
sha256:d25d4d7104a9db0136668dc442b5ec60e01ff15e9deb8a4a4ec048f6a10f9f8e

publication_hash =
sha256:d6bada1c3a9aef99ddaab718e77e2f9329b1da5821a9136f62585d2e3bb1c59b
```

The outcome is process-local and has no independent canonical artifact.

## V2 Event reuse and projection rules

First reconstruct the accepted normalization result and call the existing v1
projector. The following v2 envelope fields must equal the returned v1 Event
byte-for-byte:

- `instrument_id`;
- `event_time`;
- `available_time`;
- `phase`;
- `source_sequence`;
- `revision_id`;
- `supersedes_revision_id`;
- `source_key`;
- `source_hash`.

The retained `revision_id`/`source_hash` remain the accepted daily-member trace.
They do not become a provider revision for the catalog. The separately embedded
catalog source and binding hash commit the stock-basic member. V2 does not claim to
supersede v1 and keeps `supersedes_revision_id=null`.

V2 changes only classification, Event ID, and payload:

```text
event_id = "tushare-cn-a-share-daily-v2:" + catalog_binding_hash
stream_key = "tushare_cn_a_share.daily.publication.xshe.000001.v2"
event_type = "tushare_cn_a_share_daily_publication.v2"
capability = "tushare_cn_a_share.daily-publications@2"
```

The payload has exactly:

```text
normalization_hash
raw_bar
source_trace
execution_reference
valuation
instrument_catalog
instrument_catalog_hash
catalog_source
catalog_binding_hash
qualification
```

For the first five keys, `canonical_bytes(v2.payload[key])` must equal
`canonical_bytes(v1.payload[key])`. Do not reserialize from new DTOs, reinterpret a
price purpose, add a settlement/adjusted price, or alter any accepted v1 nested
hash. The catalog body is `json.loads(canonical_bytes(instrument_catalog))`; its
adjacent hash must equal both `canonical_sha256(instrument_catalog)` and the later
manifest field. `catalog_source` is the complete canonical source value.

`qualification` is exactly:

```text
current_metadata_only=true
provider_revision_id=null
provider_revision_closure_complete=false
revision_closure_complete=false
historical_listing_status_qualified=false
survivorship_bias_safe=false
corporate_actions_qualified=false
decision_grade_eligible=false
deployment_authorized=false
```

No field named `listing_interval`, `listed_at_event_time`, `universe`, `membership`,
`survivorship_safe`, `provider_complete`, or equivalent is permitted.

## Catalog-bound G12C/D composition

The focused composition test must pass the returned Event tuple unchanged to:

```text
validate_market_bundle_v1(
  bundle_key="tushare-cn-a-share-daily-000001-20240102-v2",
  schema_version=1,
  coverage_start=result.raw_bar.bucket.interval_start,
  coverage_end_exclusive=result.raw_bar.bucket.interval_end_exclusive,
  instrument_catalog_hash=publication.instrument_catalog_hash,
  events=(publication.market_event,),
)
```

Before publication, assert all of:

```text
manifest.instrument_catalog_hash
== publication.instrument_catalog_hash
== publication.catalog_source.instrument_catalog_hash
== publication.market_event.payload["instrument_catalog_hash"]
== canonical_sha256(publication.instrument_catalog)
```

Also reconstruct the Event-embedded body as the existing exact
`InstrumentCatalog` and require its canonical bytes/hash to match. Publish the
unchanged one-Event stream with existing `LocalMarketBundleRepository` and:

```text
retention_policy_ref = "retention.g12cd-tushare-cn-a-share-daily-v2"
```

G12C/D APIs and behavior remain unchanged. The Event embeds the body so stream and
manifest hashes transitively commit the real catalog body; the manifest's existing
catalog field commits its exact canonical hash. This is not a new repository-level
catalog member or general catalog storage contract.

## Failure contract and precedence

```text
TushareCnAShareDailyCatalogPublicationFailure@1 = {
  code: TushareCnAShareDailyCatalogPublicationFailureCode,
}
```

`failure_hash = canonical_sha256` of exact type/schema/code. Failure exposes no raw
bytes, provider text, path, exception, or credential. The seam returns exactly one
failure and no partial catalog/source/Event/result.

For any mixed-fault input, first-applicable global order is:

1. `NORMALIZATION_AUTHORITY_INVALID` — wrong result type, failed exact
   reconstruction, or failed accepted v1 projection;
2. `SNAPSHOT_SCOPE_MISMATCH` — vendor/source/license/retention provenance is not the
   exact accepted daily-listing capture scope;
3. `CATALOG_MEMBER_MISSING` — no exact `response/stock-basic.json` member metadata;
4. `CATALOG_MEMBER_BINDING_MISMATCH` — member access fails, member acquisition time
   differs from the accepted daily availability, or member/source metadata does not
   exact-bind the reconstructed snapshot;
5. `CATALOG_JSON_INVALID` — invalid UTF-8/JSON, duplicate key, or non-finite
   constant;
6. `CATALOG_SCHEMA_MISMATCH` — wrapper/data/field/type/pagination/count/row-shape
   mismatch;
7. `CATALOG_RECORD_MISMATCH` — the one row is not the exact frozen current-metadata
   row or does not exact-map to accepted `xshe:000001`;
8. `CATALOG_CONSTRUCTION_INVALID` — exact Domain catalog/source/Event/result
   reconstruction fails.

Evaluate a complete stage before advancing. With one fixed member and row there is
no positional tie. Existing v1 normalization and G12C/D failure precedence remain
unchanged because v2 neither edits nor wraps those APIs.

## RED delivery and matrix

RED commit first, production commit second. The RED commit may add only:

- `tests/bundle_builder/providers/tushare/test_cn_a_share_daily_catalog_bundle.py`;
- `tests/architecture/test_g12cd_tushare_daily_catalog_bundle_boundary.py`;
- `tests/fixtures/market_data/providers/tushare/cn-a-share-daily-bundle-v2.expected.json`.

It must fail for the missing internal v2 module/seam, not for malformed test setup.
Do not edit existing tests or fixtures.

| Area | Required RED proof |
| --- | --- |
| internal contract | exact dataclass fields/order, enum order, signature, exactly-one outcome, derived hashes |
| source grammar | duplicate/malformed JSON, bad UTF-8/constants, extra/missing keys, wrong types, pagination/count, fields/row shape |
| snapshot binding | wrong accepted-result type, constructor bypass, wrong provenance, missing member, inaccessible member, distinct member acquisition time |
| record mapping | every stock-basic column mismatch independently rejects; no generic symbol/exchange/listing inference |
| catalog | exact one CNY currency, one equity definition, no base currency, empty symbol timelines, canonical body/hash |
| source value | all raw metadata retained, exact acquisition/source/member identities, fixed false/null qualifications, hash recomputation |
| v1 reuse | five nested payload components canonical-byte-equal v1; copied envelope authority equal v1; v1 function/signature/source/fixture bytes unchanged |
| v2 distinction | Event ID/stream/type/capability distinct; no v1 supersession; exact payload and qualification keys |
| manifest binding | Event body/hash/catalog-source/binding and manifest catalog hash exact-match; forged body/hash at every layer rejected |
| G12C/D | unchanged validation, serialization, first publication, idempotent replay, ref and retention proof |
| precedence | each code alone plus mixed adjacent/all-stage faults; one failure and no partial catalog/Event/manifest/publication |
| qualification | current-metadata-only true; historical listing, survivorship, provider closure, corporate actions, decision/deployment all false |
| architecture | one new internal production module; no root export, framework, second catalog, Runtime/Kernel/network/repository/Reader import |
| compatibility | all accepted G12A/B/C/D/G and Tushare v1 fixtures/hashes/signatures remain exact |

## Frozen fixtures and hashes

Reuse unchanged:

```text
daily.json file sha256:
c2950a35c093b983e538f97830b7b3fcb0bba1a7dac98a17bd20f6db9296f846

stock-basic.json file sha256:
d78fc472268deacb5af7c59c113325e2a00c5b4619c53fbbfe6fa23c96d471d2

cn-a-share-daily-bundle-v1.expected.json file sha256:
0ccb4ebeb0f71ce45cb67c98aafd3bebd227eb01e2ccc368002660ff022e78f3
```

V1 semantic locks:

```text
normalization_hash  sha256:d01518de64eb48c9b796b83bb72eeb53fe6645d4dbcc00e88311148f23adb16c
event_hash          sha256:ab872662754a286bf9f41e722e739fe8f961d387d4d6cfa95e13888e0c8e8b0f
stream_content_hash sha256:27bb8945601e9a869e609bb8c146a998fca06878061950f294c2a0dabacd426c
manifest_hash       sha256:f343a0d9e4d86659ad0b1c73c888d050886f9713acedc77fc31fc16202fbce3f
retention_proof     sha256:77ce91f2cc959c6f8584da4d3844f436cb241b0060ed6d2e77c2f7dd2164a492
```

The new v2 expected fixture contains the complete canonical catalog, catalog source,
Event, manifest, Bundle ref, and the following independently precomputed values:

```text
catalog_hash         sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc
source_record_hash   sha256:851faa23c64268676dccdb7365b058362aae6ca3a2613752466e460bd7bb1b1e
catalog_source_hash  sha256:59d3267cbf79d4721357d5959f3e848d7a3c250802fe055b4cd40e0aa0a0b8f5
catalog_binding_hash sha256:d25d4d7104a9db0136668dc442b5ec60e01ff15e9deb8a4a4ec048f6a10f9f8e
publication_hash     sha256:d6bada1c3a9aef99ddaab718e77e2f9329b1da5821a9136f62585d2e3bb1c59b
event_hash           sha256:8ed74f580aef1b14b8ee43d55c537f8db4b5734b4b6740f3a0f5b7c36cd78015
stream_content_hash  sha256:d4dbdd709b196ed897f481455e68866c62c0cd2ca829991e76975a47fc054d8e
manifest_content_hash sha256:6a5eab718a3c6dc4ce7a5aebe9811b6e599c46b49991f7cc8a3eec66a9c3b3bb
manifest_hash        sha256:1bb2541e2131bd71d5a08cb82581fb5d035a9880ccb7fc62e5f660a0287ab6e5
retention_proof_hash sha256:22c4c7f51ecad3eed76ec94288a86b52a9e170aca0a6a01acb441b2047f73b0d
```

```text
bundle_ref = {
  type: "market_bundle_ref",
  bundle_key: "tushare-cn-a-share-daily-000001-20240102-v2",
  manifest_hash: "sha256:1bb2541e2131bd71d5a08cb82581fb5d035a9880ccb7fc62e5f660a0287ab6e5",
}
```

The v2 expected fixture is generated only in the RED delivery from these frozen
formulas and values; this plan commit does not add that fixture.

## Acceptance commands

RED proof before production:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --locked pytest -q \
  tests/bundle_builder/providers/tushare/test_cn_a_share_daily_catalog_bundle.py \
  tests/architecture/test_g12cd_tushare_daily_catalog_bundle_boundary.py
```

It must fail only because the planned v2 module/seam is absent.

Focused implementation and v1 byte locks:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --locked pytest -q \
  tests/bundle_builder/providers/tushare/test_cn_a_share_daily_catalog_bundle.py \
  tests/architecture/test_g12cd_tushare_daily_catalog_bundle_boundary.py \
  tests/bundle_builder/providers/tushare/test_cn_a_share_daily_bundle.py \
  tests/architecture/test_g12cd_tushare_daily_bundle_boundary.py \
  tests/bundle_builder/providers/tushare/test_cn_a_share_daily_normalizer.py \
  tests/architecture/test_g12b_tushare_daily_boundary.py \
  tests/bundle_builder/providers/tushare/test_cn_a_share_daily_listing_evidence.py \
  tests/bundle_builder/validation \
  tests/bundle_builder/publication

sha256sum \
  packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_daily.py \
  packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_daily_bundle.py \
  packages/market-bundle-builder/src/crypto_quant_bundle_builder/__init__.py \
  tests/fixtures/market_data/providers/tushare/cn-a-share-daily-bundle-v1.expected.json
```

Required unchanged source/file SHA-256 values are respectively:

```text
019ec74e369f8bd747342e2be5e3da8b04dfeb226a2b18a5bc49160323bac77d
561270a78ed856eb37e8e804fdde52fbcc9d52a0bac2fd1d3763e8623aa79ef9
ce723694c39feeb0f70976065f8e513a1a2277d93cc35401bbaf046520acc40e
0ccb4ebeb0f71ce45cb67c98aafd3bebd227eb01e2ccc368002660ff022e78f3
```

Broad and repository acceptance:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --locked pytest -q \
  tests/bundle_builder/providers/tushare \
  tests/bundle_builder/normalization \
  tests/bundle_builder/validation \
  tests/bundle_builder/publication \
  tests/bundle_builder/bar_aggregation \
  tests/architecture

PYTHONDONTWRITEBYTECODE=1 uv run --locked pytest -q

uv run --locked python tools/architecture/check_import_boundaries.py \
  --root . --policy architecture/import-boundaries.toml \
  --report build/acceptance/g12cd-tushare-catalog-v2-import-boundaries.json

uv lock --check
git diff --check
git status --short
```

Final acceptance requires clean detached-worktree replay, immutable RED and
implementation commits, no staged files, and independent review with no blocker or
high finding. Do not merge or push as part of this slice.

## Explicit non-goals

No historical listing interval/status, SymbolTimeline, Universe or membership
schema, survivorship certification, provider revision/checksum/correction/terminal
closure, corporate-action lifecycle or adjustment, listing containment check,
provider-wide symbol/exchange mapper, generic catalog builder, catalog repository,
G12K coverage report, G12I revision selection, G12L/G12M qualification, Runtime boot
branch, Trading Kernel dependency, decision-grade claim, live use, or deployment
authorization.
