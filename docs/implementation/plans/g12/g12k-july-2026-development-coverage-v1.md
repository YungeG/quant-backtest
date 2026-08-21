---
id: G12K-JULY-2026-DEVELOPMENT-COVERAGE-V1
readiness: BLOCKED
contract_status: D1_FROZEN_PENDING_ACCEPTANCE
owner: market-bundle-builder validation
produces:
  - UniverseCoverageReport
  - CorporateActionCoverageReport
consumes:
  - G12C MarketBundleManifest and canonical Event tuple
  - two G12B-owned normalized revision payloads
  - full-SimulationInstant closure declarations
  - synthetic xshe:xshe.corporate-action.stable InstrumentCatalog
depends_on:
  contract: [G12B, G12C, G11C, G08F]
  evidence: [synthetic-july-2026-listing-membership-action-closure-v1]
  write_conflict: [builder-coverage-policy, acceptance-registry]
---

# G12K July 2026 development coverage v1

## Status and fixed target

D1 freezes only the minimum development contract. G12K remains `DRAFT / BLOCKED`
until the payloads, declarations, RED evidence, and analyzer are implemented and
accepted. Do not update the Acceptance Matrix for D1.

The fixed target is XSHE, `EQUITY`, CNY quote/settlement, Universe
`equity.cn_a_share.xshe.corporate-action-development.v1`, point-in-time selection,
and G08F semantics `cn-a-share-record-register-entitlement-v1`, over
`[2026-07-05T16:00:00Z, 2026-07-30T16:00:00Z)` (local dates
`[2026-07-06, 2026-07-31)` in `Asia/Shanghai`).

Use a new canonical `InstrumentCatalog` containing only CNY and the exact
`InstrumentDefinition(EQUITY, xshe:xshe.corporate-action.stable, base=None,
quote=CNY, settlement=CNY)`, with no symbol timelines. Its canonical hash is
`sha256:954cac9b51cdfae55bcf0f5dd6fbcbda5c7c353baca43fd00fcddeb6c34104bb`.
It must bind the G12C manifest and must not reuse the incompatible Tushare
`xshe:000001` catalog hash
`sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc`.

## Complete G12B payload schemas

The two exact frozen dataclasses live in
`crypto_quant_bundle_builder.g12b_universe_corporate_action_payloads`, are not
root exports, and expose `to_canonical_dict()` plus a computed `payload_hash`.
`to_canonical_dict()` appends `payload_hash` after the fields shown, and the exact
`MarketEvent.payload` is that complete canonical mapping. The analyzer validates
that hash and deep-reconstructs the mapping to the exact payload class; an Event
never contains a Python payload object. Unknown keys, coercion, subclasses, and
constructor-bypass values fail reconstruction.

### `G12BListingMembershipRevisionPayloadV1`

```text
type: ClassVar[str] = "g12b_listing_membership_revision"
schema_version: ClassVar[int] = 1
universe_key: str
membership_key: str
listed_at: UtcInstant
delisted_at: UtcInstant | None
member_from: UtcInstant
member_until: UtcInstant | None
```

Its exact Event stream is `g12k.universe.listing-membership`, event type is
`listing_membership_revision`, and capability is
`MarketBundleCapability("universe", 1)`. The parity mapper injects the frozen
G11C constant `UniverseKind.POINT_IN_TIME`; it is not repeated in the payload.
The Event envelope supplies `instrument_id`, `timeline_instant` as `available_at`,
`revision_id`, `supersedes_revision_id`, and `source_hash`, producing every G11C
`UniverseMembershipRevision` field one-for-one. Listing and membership are
non-empty half-open intervals, membership is contained by listing, and the Event
Instrument exact-matches the synthetic catalog.

### `G12BCorporateActionStatusV1`

Exact enum values are `FINAL_IMPLEMENTATION = "final_implementation"`,
`PLAN_ONLY = "plan_only"`, and `CANCELLED = "cancelled"`.

### `G12BCorporateActionLifecycleRevisionPayloadV1`

```text
type: ClassVar[str] = "g12b_corporate_action_lifecycle_revision"
schema_version: ClassVar[int] = 1
corporate_action_id: str
status: G12BCorporateActionStatusV1
calendar_id: str
record_date: str | None
ex_date: str | None
payment_date: str | None
listing_date: str | None
cash_per_share_units: int | None
cash_per_share_scale: int | None
cash_currency: str | None
bonus_rate_units: int | None
bonus_rate_scale: int | None
bonus_rate_basis: str | None
capitalization_rate_units: int | None
capitalization_rate_scale: int | None
capitalization_rate_basis: str | None
```

Its exact Event stream is `g12k.corporate-actions.lifecycle`, event type is
`corporate_action_lifecycle_revision`, and capability is
`MarketBundleCapability("corporate_actions", 1)`. The parity mapper injects the
frozen G08F semantics key; it is not repeated in the payload. The catalog supplies
the exact `InstrumentDefinition`; the Event envelope supplies candidate Event,
revision, source, event-time, and full availability identities. G08F
`source_refs` is the singleton Event `(source_key, source_hash)`.

`calendar_id` is exactly `CN.XSHE`. Date values are canonical ISO `YYYY-MM-DD`
strings because `MarketEvent.payload` does not admit Python `date`; the parity
mapper parses them to `TradingDate`. `FINAL_IMPLEMENTATION` requires Record and
Ex plus at least one positive distribution term; cash is CNY Scale 2 and requires
Payment, and bonus/capitalization require Listing with basis `shares_per_share`.
`PLAN_ONLY` may be non-terminal only. `CANCELLED` must be terminal and has no
lifecycle or distribution terms. G12K validates field presence, canonical dates,
positive terms, exact cash scale/bases, and the frozen Record-date relevance rule
below. It does not infer trading days or enforce Ex/Payment/Listing ordering;
those calendar-derived checks remain with G08F and its calendar authority. No
register, entitlement, account, tax, Journal, Ledger, Lot, payment effect, or
delivery field is admitted.

## One complete closure schema

Reuse existing Builder `RevisionTerminalLineage`; do not add another terminal
shape. Its existing exact schema remains:

```text
type: "revision_terminal_lineage"
schema_version: 1
logical_lineage_key: str
terminal_event_hash: str
```

Add one generic `G12KRevisionClosureDeclarationV1` and instantiate it once per
scope. `G12KCoverageScopeV1` has exact values `UNIVERSE = "universe"` and
`CORPORATE_ACTIONS = "corporate_actions"`.

```text
type: ClassVar[str] = "g12k_revision_closure_declaration"
schema_version: ClassVar[int] = 1
scope: G12KCoverageScopeV1
context_key: str
target_start: UtcInstant
target_end_exclusive: UtcInstant
causal_visibility_limit: SimulationInstant
event_hashes: tuple[str, ...]
terminals: tuple[RevisionTerminalLineage, ...]
source_key: str
source_hash: str
declaration_hash: computed sha256 property, appended by to_canonical_dict()
```

The Universe instance uses context key
`equity.cn_a_share.xshe.corporate-action-development.v1|point_in_time|xshe:xshe.corporate-action.stable`;
the action instance uses
`cn-a-share-record-register-entitlement-v1|CN.XSHE|xshe:xshe.corporate-action.stable`.
Both use the fixed target interval. Event hashes are sorted and unique. Terminals
are sorted by unique `logical_lineage_key`. Declaration presence with both tuples
empty is the sole explicit-empty closure; one empty and one non-empty tuple is
invalid. No explicit-empty boolean exists.

Universe lineages use `membership_key`; action lineages use
`corporate_action_id`. Every declared Event is available at or before
`causal_visibility_limit`. Each non-empty lineage has exactly one root and the
one declared terminal; revision IDs are unique; every non-root names its immediate
parent; each parent has at most one child; traversal visits every node once; and
forks, cycles, missing/disconnected nodes, or extra roots/terminals fail. A child
`MarketEvent.timeline_instant` is strictly later than its parent under the full
`SimulationInstant` total order. Lineage scope identity cannot change: Universe identity is exactly
`(universe_key, membership_key, instrument_id)` and action identity is exactly
`(corporate_action_id, calendar_id, instrument_id)`.

A correction fully replaces its parent payload. A terminal action cancellation
closes the lineage and remains in relevant/terminal evidence. Empty member/action
success requires the corresponding present, scope-correct empty declaration;
missing declarations or undeclared absence fail.

## Candidate selection, reconstruction, and analyzer

Add one non-root-exported pure Builder module,
`crypto_quant_bundle_builder.g12k_july_2026_development_coverage`:

```python
analyze_g12k_july_2026_development_coverage_v1(
    *,
    manifest: MarketBundleManifest,
    instrument_catalog: InstrumentCatalog,
    events: tuple[MarketEvent, ...],
    universe_closure: G12KRevisionClosureDeclarationV1,
    corporate_action_closure: G12KRevisionClosureDeclarationV1,
) -> G12KJuly2026DevelopmentCoverageOutcome
```

Inputs are exact concrete types/tuples. First rerun unchanged
`validate_market_bundle_v1()` from the supplied manifest fields and Events; use
its Event reconstruction and require exact equality with the supplied manifest.
Do not reconstruct Event envelopes again. Only after G12C success, deep-reconstruct
the catalog, the two payload bodies, and both declarations. A top-level exact-type
failure is `INVALID_INPUT`; a canonical declaration reconstruction failure is
`CLOSURE_MISMATCH` for that declaration's scope.

Candidate selection precedes classification. Partition every G12C-validated Event
by the two exact stream keys; an Event in neither stream fails, so a malformed
near-match cannot be ignored. Then require every candidate's exact event type,
capability, Instrument, and payload mapping to deep-reconstruct to the selected
scope's exact class. Each closure's `event_hashes` must equal its entire selected
candidate hash set. Candidate validation is input-order independent: sort each
scope's candidates by Event hash before validation.

## Deterministic coverage semantics

Universe coverage uses `decision_instant = universe_closure.causal_visibility_limit`
as the full-time evidence cutoff and `effective_at = target_start` as the sole
membership inclusion instant. For each terminal lineage visible by that decision
instant, select its Instrument exactly when both terminal listing and membership
half-open intervals contain `effective_at`. Distinct selected lineages may not
select the same Instrument. A gap before/after `effective_at`, or a terminal
interval not containing it, is valid and makes that lineage unselected; G12K
makes no full-target membership continuity claim. A present empty closure
produces an empty member tuple.

Action coverage uses Record date as its sole relevance date and partitions every
terminal lineage exactly once. A terminal `FINAL_IMPLEMENTATION` uses its own
Record date. A terminal `CANCELLED` uses the nearest ancestor in its linear chain
with a non-null Record date; no such ancestor is a coverage failure. When that
relevance date is inside local `[2026-07-06, 2026-07-31)`, final implementations
contribute to `active_corporate_action_ids` and cancellations contribute to
`cancelled_corporate_action_ids`. A terminal lineage with relevance outside the
range is valid and contributes to neither tuple. Terminal `PLAN_ONLY`,
non-terminal cancellation, duplicate action ID, or ambiguous relevance fails. A
present empty closure produces both empty action-ID tuples.

## Complete output schemas

Every canonical body contains fields in the order shown. Hash properties are
computed over the body and appended by `to_canonical_dict()`.

### `UniverseCoverageReport`

Canonical body type `universe_coverage_report`, schema version 1:

```text
manifest_content_hash: str
instrument_catalog_hash: str
closure_declaration_hash: str
target_start: UtcInstant
target_end_exclusive: UtcInstant
decision_instant: SimulationInstant      # exact closure causal_visibility_limit
effective_at: UtcInstant                 # exact target_start
relevant_event_hashes: tuple[str, ...]
terminal_event_hashes: tuple[str, ...]
member_instrument_ids: tuple[InstrumentId, ...]
declared_revision_closure_complete: bool # exact true
provider_authority_qualified: bool       # exact false
provider_revision_completeness_qualified: bool # exact false
historical_authority_qualified: bool     # exact false
survivorship_bias_safe: bool             # exact false
decision_grade_eligible: bool            # exact false
profile_qualified: bool                  # exact false
live_eligible: bool                      # exact false
deployment_authorized: bool              # exact false
report_hash: computed sha256 property
```

### `CorporateActionCoverageReport`

Canonical body type `corporate_action_coverage_report`, schema version 1:

```text
manifest_content_hash: str
instrument_catalog_hash: str
closure_declaration_hash: str
target_start: UtcInstant
target_end_exclusive: UtcInstant
relevant_event_hashes: tuple[str, ...]
terminal_event_hashes: tuple[str, ...]
active_corporate_action_ids: tuple[str, ...]
cancelled_corporate_action_ids: tuple[str, ...]
declared_revision_closure_complete: bool # exact true
provider_authority_qualified: bool       # exact false
provider_revision_completeness_qualified: bool # exact false
historical_authority_qualified: bool     # exact false
survivorship_bias_safe: bool             # exact false
decision_grade_eligible: bool            # exact false
profile_qualified: bool                  # exact false
live_eligible: bool                      # exact false
deployment_authorized: bool              # exact false
report_hash: computed sha256 property
```

Every report tuple is unique and canonically ordered: Event-hash tuples are
ascending lexicographic hashes, Instrument IDs are ascending by canonical ID text,
and corporate-action IDs are ascending strings. `declared_revision_closure_complete=true`
is only mechanical consistency against the supplied canonical declarations. It
is distinct from provider/archive revision completeness and cannot elevate any
frozen qualification flag.

### Failure and outcome

`G12KJuly2026DevelopmentCoverageFailureCode` exact serialized values, in
precedence order:

1. `INVALID_INPUT = "invalid_input"`
2. `G12C_VALIDATION_FAILED = "g12c_validation_failed"`
3. `BUNDLE_MANIFEST_MISMATCH = "bundle_manifest_mismatch"`
4. `CATALOG_EVENT_BINDING_MISMATCH = "catalog_event_binding_mismatch"`
5. `EVENT_CONTRACT_MISMATCH = "event_contract_mismatch"`
6. `CLOSURE_MISMATCH = "closure_mismatch"`
7. `COVERAGE_SEMANTICS_MISMATCH = "coverage_semantics_mismatch"`

`CATALOG_EVENT_BINDING_MISMATCH` covers catalog reconstruction/hash/body,
manifest catalog binding, unknown Event Instrument, and Event/catalog definition
mismatch.

`G12KJuly2026DevelopmentCoverageFailure` canonical body type
`g12k_july_2026_development_coverage_failure`, schema version 1:

```text
code: G12KJuly2026DevelopmentCoverageFailureCode
scope: G12KCoverageScopeV1 | None
logical_lineage_key: str | None
failure_hash: computed sha256 property
```

Top-level/G12C/manifest/catalog failures have no scope or lineage key. Scope is
present for scope-specific Event, closure, or coverage failures. The lineage key
is present only after a failing lineage is deterministically known; otherwise it
is absent. Within one failure category, attribution checks Universe before
Corporate Actions, then ascending `logical_lineage_key`, then ascending Event
hash; the first failure wins. Failure carries no exception text or partial report.

`G12KJuly2026DevelopmentCoverageOutcome` canonical body type
`g12k_july_2026_development_coverage_outcome`, schema version 1:

```text
universe_report: UniverseCoverageReport | None
corporate_action_report: CorporateActionCoverageReport | None
failure: G12KJuly2026DevelopmentCoverageFailure | None
outcome_hash: computed sha256 property
```

Strict XOR permits only both reports with no failure, or one failure with both
reports absent. The analyzer returns both reports atomically or one failure.

## Test matrix

| Case | Frozen result |
| --- | --- |
| Canonical member plus corrected final action | Both reports; repeat bytes/hashes equal |
| Present empty declaration for either/both scopes | Success with corresponding empty tuples |
| One empty and one non-empty closure tuple; missing/wrong scope/context; declaration reconstruction failure | `CLOSURE_MISMATCH` |
| G12C invalid Event/order | `G12C_VALIDATION_FAILED` before G12K work |
| Rebuilt manifest differs | `BUNDLE_MANIFEST_MISMATCH` |
| Tushare hash, catalog mutation, unknown/mismatched Event Instrument | `CATALOG_EVENT_BINDING_MISMATCH` |
| Unknown stream or malformed expected-stream type/capability/payload | `EVENT_CONTRACT_MISMATCH`; never ignored |
| Omitted/extra hash, root/terminal/parent/fork/cycle/disconnection, full-time regression | `CLOSURE_MISMATCH` |
| Membership containment/duplicate selected Instrument, terminal action state/terms/Record-date partition | `COVERAGE_SEMANTICS_MISMATCH` |
| Equal UTC with strictly later phase/sequence | Accepted full-time child ordering |
| G11C test-only parity | Exact revision field/hash mapping with injected point-in-time kind |
| G08F test-only parity | Narrow exact Candidate field/hash mapping with injected semantics and parsed ISO dates; no calendar-derived lifecycle claim, register, or economics |
| Qualification mutation | Constructor/deep reconstruction rejects any true flag |
| Meaningful precedence combinations | G12C over catalog/Event; catalog over Event; Event over closure; closure over semantics |
| Architecture/static scan | Builder only; no Runtime/Kernel, I/O, root export, registry/framework/repository |

Each of the seven failure branches receives one direct test; do not create an
adjacent-pair combinatorial matrix.

## Expected implementation write set

D1 changes documentation only. A later approved implementation is limited to:

```text
packages/market-bundle-builder/src/crypto_quant_bundle_builder/g12b_universe_corporate_action_payloads.py
packages/market-bundle-builder/src/crypto_quant_bundle_builder/g12k_july_2026_development_coverage.py
tests/bundle_builder/coverage/test_g12k_july_2026_development_coverage.py
tests/architecture/test_g12k_july_2026_development_coverage_boundary.py
tests/fixtures/bundle_builder/g12k-july-2026-development-coverage-v1.json
```

Reuse `coverage_declarations.RevisionTerminalLineage`; do not edit it. No package
`__init__.py`, Runtime, Kernel, G12C, catalog/domain schema, repository,
registry/framework, or Acceptance Matrix write is expected.

## D1 acceptance and exclusions

D1 is accepted only when this subplan and the two parent links are the entire
diff; all schemas and deterministic semantics above receive required reviewer
approval; Markdown/LSP/link, `git diff --check`, and gitleaks pass; and Git has no
staged files. D1 does not change readiness or authorize production/tests.

No provider/history/survivorship claim, interval-wide Universe guarantee,
identifier mapping, inferred lifecycle, entitlement/register/accounting, tax,
fractional-share handling, Reader/repository/I/O, Runtime/Kernel integration,
root export, framework, registry, profile/live/deployment qualification, commit,
push, staging, or Acceptance Matrix update.
