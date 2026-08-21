---
id: G12L-BINANCE-USDM-FUNDING-HISTORY-SOURCE-BOUNDED-V2
readiness: CONTRACT_FROZEN
gate_status: D1_PASSED
owner: market-bundle-builder Binance USD-M source observation
produces:
  - BinanceUsdmFundingHistorySourceBoundedObservationReportV2
consumes:
  - ADR 0008
  - existing Binance funding-history acquisition tool
  - exact Binance USD-M Funding Rate History REST response and receipt
  - G12A SourceSnapshot
  - G12C validation and G12D publication contracts
depends_on:
  contract: [G10E, G12A, G12C, G12D, G12L-BINANCE-USDM-FUNDING-HISTORY-V1]
  evidence:
    - accepted exact REST response sha256:e9f73f9c845c28abb31037d8230df2d6f13d5d368c43436e891fcc757372c338
    - live replayed capture with identical response bytes
  write_conflict: [provider-observation-policy, acceptance-registry]
fan_out: [G12M-SOURCE-BOUNDED-QUALIFICATION-V1]
---

# G12L Binance USD-M Funding History source-bounded v2

## Status and purpose

D1 is frozen and passed. This additive v2 reclassifies the exact finite Binance
Funding Rate History REST evidence under ADR 0008. The absence of a permanent
provider checksum, proof of no future revision, complete correction lineage, or
provider-global completeness remains an explicit limitation rather than an
ordinary historical-research blocker.

The slice normalizes and publishes the exact three observed funding records with
their funding-time mark prices. It does not modify the accepted monthly rate-only
v1 archive, G10E, Runtime, Kernel, Builder root, existing fixtures, or public APIs.
It grants no result grade, profile, live, or deployment authority.

## Frozen source scope

- provider: `binance.fapi`;
- endpoint: `GET https://fapi.binance.com/fapi/v1/fundingRate`;
- symbol: `BTCUSDT`;
- instrument: `binance_usdm:btc-usdt-perpetual`;
- `startTime=1704067200000`;
- `endTime=1704153599999`;
- `limit=100`;
- request URL:
  `https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&startTime=1704067200000&endTime=1704153599999&limit=100`;
- request scope hash:
  `sha256:e749c6265a08ebc7095c96c3636e3070eceb3f5cd82e2e981d9d23167ef50be1`;
- coverage: UTC `[2024-01-01T00:00:00Z, 2024-01-02T00:00:00Z)`;
- exact expected funding times: `1704067200000`, `1704096000000`, and
  `1704124800000` milliseconds;
- exactly three records, strictly increasing, all below `limit`;
- no authentication, signature, pagination fallback, latest/current fallback,
  symbol discovery, nearby kline, manufactured mark, forward fill, or resampling.

The exact request-scope preimage is:

```text
{
  "type": "binance_usdm_funding_history_acquisition_request",
  "schema_version": 1,
  "symbol": "BTCUSDT",
  "start_time_milliseconds": 1704067200000,
  "end_time_milliseconds": 1704153599999,
  "limit": 100,
  "url": "https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&startTime=1704067200000&endTime=1704153599999&limit=100",
}
```

`request_scope_hash = canonical_sha256(exact request-scope preimage)`.

The endpoint result is observed-as-of local receipt time. It is not asserted to be
an immutable 2024 publication or provider-final revision.

## Frozen live capture candidate

The accepted acquisition tool was run again against the exact request. The new
capture returned byte-identical response content:

```text
response_sha256: sha256:e9f73f9c845c28abb31037d8230df2d6f13d5d368c43436e891fcc757372c338
response_byte_count: 379
receipt_sha256: sha256:a92989478047de7d744744aedeaf365f7d16240b536c1ccece749abe3b4efa36
acquired_at_epoch_nanoseconds: 1787304863983843230
snapshot_id: sha256:a45d9acdcfb4d42d1c70af44969f6a5151fb260c4c3040943b3d961c1073aa3f
content_tree_hash: sha256:b992587527ddb79b5d752a0bc060cad8bdfd960b874f194d49f16033f171dfd0
provenance_hash: sha256:8591a52c953f11179a3ddc59e9c16db7d28518d7220643f73b31967683e760f6
attempts: 1
record_count: 3
missing_mark_price_count: 0
```

The v2 fixture stores the raw response under
`response/funding-history.json` while preserving the receipt's exact
`response/funding-history.json` SourceSnapshot member key.

## Exact acquisition receipt

D2 reuses, without modification,
`tools/acquisition/binance_usdm.py::acquire_funding_history`. The canonical receipt
must have exactly these fields in order:

```text
acquired_at_epoch_nanoseconds
attempts
decision_grade_eligible
deployment_authorized
missing_mark_price_count
record_count
request
response_sha256
schema_version
snapshot
type
```

Required values for every observation:

- type `binance_usdm_funding_history_acquisition_receipt`, schema `1`;
- exact frozen request mapping and request scope hash above;
- receipt, response, Snapshot, member, and observation identities that agree
  internally with the supplied evidence;
- `decision_grade_eligible=false` and `deployment_authorized=false`;
- one SourceSnapshot member `response/funding-history.json`, mode `0644`, content
  hash equal to the response hash, and null declared hash; the first accepted
  candidate byte count is `379`, while later observations derive and verify byte
  count from their supplied raw bytes/Snapshot;
- provenance vendor `binance.fapi`, source key
  `binance.fapi.funding_rate_history.btcusdt.1704067200000.1704153599999`,
  license `binance.api.terms`, retention
  `backtest.acquisition.candidate`.

The exact candidate identities listed above are mandatory only for the first
accepted fixture/report. A later corrected observation retains the frozen request
and provenance scope but has newly derived receipt, response, Snapshot, member,
observation, Event, manifest, and report identities.

Receipt parsing rejects duplicate keys, invalid constants, noncanonical bytes,
unknown/missing keys, booleans substituted for integers, and arbitrary exception
text. No secret, cookie, header, environment value, or undeclared path is retained.

## Exact response and source-row replay

The response is a compact UTF-8 JSON array with no CR and no trailing bytes. Every
item has exactly these keys in order:

```text
symbol
fundingTime
fundingRate
markPrice
rateType
```

Each retained canonical source row is exactly:

```text
(symbol, funding_time_milliseconds, funding_rate_lexeme,
 mark_price_lexeme, rate_type)
```

The source-row hash is:

```text
canonical_sha256({
  "fields": ("symbol", "fundingTime", "fundingRate", "markPrice", "rateType"),
  "row": source_row,
})
```

Requirements:

- symbol is exactly `BTCUSDT`;
- funding time is exact integer and one of the three frozen times;
- funding rate is an exact signed decimal matching
  `-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,18})?`, with length at most 64 and no negative
  zero;
- mark price is an exact positive decimal matching
  `(?:0|[1-9][0-9]*)(?:\.[0-9]{1,18})?`, with length at most 64 and numeric value
  strictly greater than zero;
- leading plus, exponent syntax, leading-zero whole parts, empty fractions, NaN,
  infinities, and other JSON numeric forms are rejected;
- rate type is exactly `Regular`;
- records retain provider order and are never deduplicated;
- response hash, receipt count, missing-mark count, Snapshot member, and raw bytes
  must all agree.

## Exact normalization and publication

D3 normalizes both decimal fields at scale `8` with exact `Decimal` semantics:

- the response-schema stage applies the exact grammar and bounds above;
- the normalization stage requires `Decimal(lexeme) * 10^8` to be an exact integer;
  more precise nonzero digits fail rather than round;
- canonical decimal string has exactly eight fractional digits;
- `funding_rate_units = decimal * 10^8` and may be signed;
- `mark_price_units = decimal * 10^8` and must be positive;
- no float conversion, quantization rounding, inferred mark, or nearby price lookup
  is allowed.

D3 emits exactly three `MarketEvent` values:

```text
stream_key: binance_usdm.funding_history.publications.btcusdt.v2
event_type: binance_usdm_funding_history_publication.v2
capability: MarketBundleCapability("binance_usdm.funding-publications", 2)
instrument_id: binance_usdm:btc-usdt-perpetual
event_time: fundingTime
available_time: receipt acquired_at
timeline phase: (0, "market_data")
source_sequence: provider row index
revision_id: raw response content hash
supersedes_revision_id: null
source_key: frozen SourceSnapshot provenance source key
source_hash: raw response content hash
```

For each row, the Event identity preimage is:

```text
{
  "type": "binance_usdm_funding_history_event_identity",
  "schema_version": 2,
  "snapshot_id": snapshot.snapshot_id,
  "funding_time_milliseconds": source_row[1],
  "source_record_hash": source_record_hash,
}
```

`event_id = "binance-usdm-funding-history-v2:" +
canonical_sha256(Event identity preimage)`.

Each payload has exactly:

```text
funding_purpose
funding_time_milliseconds
raw_funding_rate
funding_rate
funding_rate_units
funding_rate_scale
raw_mark_price
mark_price
mark_price_units
mark_price_scale
rate_type
source_record_hash
```

`funding_purpose="funding"`; both scales are `8`. Event identity and event hash are
deterministic from the exact source row, Snapshot, and normalized payload.

G12C validation is frozen to:

```text
bundle_key: binance-usdm-funding-history-btcusdt-2024-01-01-source-bounded-v2
schema_version: 1
coverage_start: 1704067200000000000 ns
coverage_end_exclusive: 1704153600000000000 ns
instrument_catalog_hash: sha256:0000000000000000000000000000000000000000000000000000000000000000
```

The zero catalog hash is retained only for compatibility with accepted Binance
Builder slices and is an explicit limitation, not catalog authority. The exact
stream payload is `canonical_bytes(events)` and its manifest content hash is
`canonical_sha256(events)`. D3 builds and replays the exact events, stream payload,
manifest, and `MarketBundleRef` in memory. Tests pass that same stream payload to
G12D publication in a temporary repository; production D3 performs no filesystem
I/O.

## Exact observer interface

D3 may add only these provider-specific symbols:

```text
BinanceUsdmFundingHistorySourceBoundedObservationReportV2
BinanceUsdmFundingHistorySourceBoundedObservationOutcomeV2
observe_binance_usdm_funding_history_source_bounded_v2(
  *,
  acquisition_receipt_bytes: bytes,
  snapshot: SourceSnapshot,
  supersedes_report: BinanceUsdmFundingHistorySourceBoundedObservationReportV2 | None = None,
  supersedes_acquisition_receipt_bytes: bytes | None = None,
  supersedes_snapshot: SourceSnapshot | None = None,
) -> BinanceUsdmFundingHistorySourceBoundedObservationOutcomeV2
```

The observer requires exact types, verifies receipt/Snapshot/raw bytes, validates
scope and response, and normalizes rows. It then preflights that receipt availability
is later than every funding event time before constructing Events, builds/replays
exact Event IDs/hashes, `canonical_bytes(events)`, the G12C manifest, and Bundle ref,
and deep-reconstructs the completed report.

## Exact report

The canonical report body fields are ordered exactly as follows, followed by
computed `report_hash`:

```text
type
schema_version
provider_key
datasets
instrument_id
coverage_start
coverage_end_exclusive
request_scope_hash
acquisition_receipt_sha256
snapshot_id
snapshot_content_tree_hash
provenance_hash
member_keys
member_content_hashes
member_acquired_at_epoch_nanoseconds
response_record_count
missing_mark_price_count
source_rows
source_record_hashes
bundle_ref
manifest_content_hash
stream_content_hash
published_event_hashes
observed_at
supersedes_report_hash
limitations
availability_closure_complete
revision_closure_complete
provider_authority_qualified
provider_revision_completeness_qualified
instrument_catalog_qualified
decision_grade_eligible
profile_qualified
live_eligible
deployment_authorized
```

Fixed invariants:

- type `binance_usdm_funding_history_source_bounded_observation_report`, schema `2`;
- provider `binance.fapi`, datasets `("fundingRate",)`;
- exact instrument, request, coverage, and internally consistent Snapshot, receipt,
  and member identities;
- exactly three replayable source rows and source-record hashes;
- exactly three deterministic Event hashes and one-stream manifest/Bundle ref;
- `observed_at` equals receipt/member acquisition time;
- first accepted `supersedes_report_hash` is null;
- all qualification flags are exact bool and false.

The exact limitations tuple is:

```text
(
  "permanent_provider_checksum_unavailable",
  "future_revision_finality_unknown",
  "provider_correction_lineage_unavailable",
  "provider_completeness_unknown",
  "current_api_capture_is_not_immutable_publication",
  "local_observation_time_is_late_for_event_time",
  "single_symbol_single_day_scope",
  "instrument_catalog_authority_unavailable",
)
```

`report_hash = canonical_sha256(complete body excluding report_hash)`.
`from_canonical_dict()` reconstructs the exact compact raw response bytes from
`source_rows` using the frozen field order, requires their SHA-256 to equal the
single member content hash, then rebuilds the one-member `SourceSnapshot` with the
reported acquisition time and frozen provenance and compares snapshot, content-tree,
and provenance hashes before replaying Events and publication. It rejects
unknown/missing keys, coercion, nested substitution, constructor bypass, source
rows/hashes/raw/Snapshot/Event/manifest inconsistencies, or any true qualification
flag. Receipt SHA-256 remains bound where receipt bytes are available: the observer,
first acceptance, and predecessor-evidence replay.

## Failure precedence

The outcome contains exactly one report or one failure. First applicable trigger
wins:

1. `INVALID_INPUT` — wrong exact input type;
2. `EVIDENCE_INVALID` — receipt/Snapshot/member/hash/time/canonical/security binding
   fails;
3. `REQUEST_SCOPE_MISMATCH` — request/provenance/source scope differs;
4. `RESPONSE_SCHEMA_MISMATCH` — envelope, key order, row shape, primitive, or
   decimal grammar differs;
5. `RESPONSE_SCOPE_MISMATCH` — symbol, times, order, count, rate type, or mark
   presence differs;
6. `NORMALIZATION_FAILED` — exact scale conversion or economic invariant fails;
7. `LOOKAHEAD_VIOLATION` — observed availability is not later than every funding
   event time; this preflight runs before Event construction;
8. `PUBLICATION_FAILED` — Event, stream payload, manifest, or Bundle-ref replay
   fails;
9. `PREDECESSOR_INVALID` — predecessor inputs are partial, malformed, or cannot be
   rebuilt exactly from supplied receipt/Snapshot/raw evidence;
10. `CORRECTION_EDGE_INVALID` — fixed scope differs, snapshot is unchanged, or new
    observed time is not later;
11. `REPORT_BINDING_MISMATCH` — completed report reconstruction disagrees.

Failure data is code plus optional member key only. It never contains provider raw
text, arbitrary exception text, secret material, or undeclared paths.

## Append-only correction semantics

Either all predecessor inputs are absent or all are present with exact types. D3
independently replays the predecessor receipt, Snapshot, raw response, source rows,
Events, manifest, Bundle ref, and complete report while preserving only its already
recorded prior-edge hash. The new direct edge requires identical fixed scope, a new
snapshot, and later observation time, and sets
`supersedes_report_hash=predecessor.report_hash`.

D3 does not infer repository head, omitted intermediates, forks, or provider
correction lineage. Acceptance policy establishes currentness. Old evidence,
reports, Runs, and results remain immutable.

## Architecture and nonclaims

- Production D3 has no network or filesystem I/O.
- Builder does not import Runtime or Kernel; Runtime does not import Builder.
- No root export, second Binance client, provider registry, generic source
  framework, facts registry, cache, repository, resampler, or policy DSL is added.
- Existing acquisition tool, v1 Funding History evidence, monthly Funding Rate v1,
  G10E, and accepted fixtures/APIs remain byte-identical.
- The response proves exact observed rate+mark rows only. It does not prove provider
  finality, immutable publication identity, completeness outside the finite request,
  live correctness, or deployment authority.

## D2 — accepted-tool capture (unimplemented)

Authorized write set:

```text
tests/fixtures/market_data/providers/binance_usdm/funding-history-source-bounded-v2/response/funding-history.json
tests/fixtures/market_data/providers/binance_usdm/funding-history-source-bounded-v2/acquisition-receipt.json
tests/tools/acquisition/test_binance_usdm_funding_history_source_bounded_v2.py
tests/architecture/test_g12l_binance_funding_history_source_bounded_boundary.py
```

D2 copies the exact live candidate bytes, reproduces them through the unchanged
accepted acquisition function using a bounded fake transport, verifies no-clobber
publication and canonical receipt/Snapshot identity, and runs secret scans.

## D3 — observation, normalization, and publication (unimplemented)

Authorized write set:

```text
packages/market-bundle-builder/src/crypto_quant_bundle_builder/binance_usdm_funding_history_source_bounded_v2.py
tests/bundle_builder/providers/binance_usdm/test_funding_history_source_bounded_v2.py
tests/architecture/test_g12l_binance_funding_history_source_bounded_boundary.py
tests/fixtures/market_data/providers/binance_usdm/funding-history-source-bounded-v2/observation-report.expected.json
```

D3 exits only after exact evidence reconstruction, row/Event/manifest replay,
G12C validation, temporary G12D publication, lookahead, correction, failure
precedence, architecture, protected-byte, LSP, lint, diff, and secret checks pass.

## D4 — acceptance and G12M handoff (unimplemented)

Authorized documentation write set:

```text
docs/implementation/plans/g12/g12l-binance-usdm-funding-history-source-bounded-v2.md
docs/implementation/plans/g12/g12l-binance-usdm-funding-history-v1.md
docs/implementation/plans/g12/g12m-source-bounded-qualification-v1.md
docs/implementation/plans/g12/README.md
docs/implementation/acceptance-matrix.md
```

D4 records exact response, receipt, Snapshot, row, Event, manifest, report, file,
plan, and immutable implementation identities. It may make one exact Binance
funding-history G12M case provider-specifically nominally ready, but it authorizes
no generic Runtime interface, grade change, provider finality, live use, or
deployment.
