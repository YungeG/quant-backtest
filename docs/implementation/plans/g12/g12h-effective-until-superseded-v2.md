---
id: G12H-EFFECTIVE-UNTIL-SUPERSEDED-V2
readiness: BLOCKED_ON_ACCESS_PRODUCT_DISCRIMINATOR
gate_status: DRAFT
owner: official-source acquisition + trading-kernel projection + market-bundle-builder publication
produces:
  - official-rule successor-closure artifact v1
  - finite target-scoped fee/tax RuleBooks
  - additive five-dimension declaration and G12C/D publication v2
  - G12H RuleCoverageReport or RuleCoverageFailure contract
consumes:
  - exact official predecessor, endpoint, and successor-index evidence
  - immutable G08E/G08H and G12C/D v1 identities
  - ADR 0004 effective-until-authoritatively-superseded semantics
depends_on:
  contract: [G08E, G08H, G12C, G12D]
  evidence: [real XSHE July-2026 successor closure]
  write_conflict: [kernel-cn-a-share-fee-tax, builder-rule-publication, acceptance-registry]
fan_out: [G12H, G12L-*, G12M-*]
---

# G12H Effective-Until-Authoritatively-Superseded v2

## Status and authority

`BLOCKED`. Initial F1 research proves the existing fee query cannot enforce the full official fee envelope: domestic and Northbound access differ, and ordinary shares, preferred stock, and Northbound ETFs have different fee schedules. Further closure acquisition and F2/F3 remain blocked until an additive execution-enforced access-route and fee-product-class contract—or another explicitly enforceable narrower scope—is approved. No default or silent Stock Connect exclusion is permitted.

Accepted semantics: [ADR 0004](../../../adr/0004-official-rules-effective-until-authoritatively-superseded.md).

Evidence baseline:

- [G12H five-dimension blocker](../../../research/g12h-five-dimension-target-coverage-blocker-v1.md);
- [G12H rule-coverage analysis](../../../research/g12h-rule-coverage.md);
- [XSHE July-2026 fee/tax source research](../../../research/g12h-xshe-july-2026-fee-tax-authority-primary-sources.md);
- [F1 full-envelope access/product blocker](../../../research/g12h-xshe-july-2026-full-envelope-successor-closure-f1.md).

The existing v1 declaration still deterministically fails `COVERAGE_GAP / market_fees`. No existing PASSED G08E, G08H, G12C/D, fixture, hash, event, manifest, test, or publication byte may change.

## Frozen decision

A scoped official rule revision is economically effective from its authoritative start until a competent authority makes an authoritative successor effective. Documentary correction and economic succession are independent: `corrects_revision_id` links representations of the same official act, while `economic_predecessor_revision_id` links complete economic states across official acts. At cutoff, closure selects the terminal documentary representation of each act, then orders selected economic states by authoritative `effective_from`; publication, capture, and tuple order never decide economic order. Retroactive correction is allowed, including one recorded after target end that changes a target segment. Unresolved documentary/economic forks, gaps, overlaps, or conflicts fail closed.

Source-law continuity is not an execution interval: a successful closure is projected to one finite target and materialized with the existing finite `CnAShareMarketFeeBand`, `CnAShareStampDutyBand`, `CnAShareMarketFeeRuleBook`, and `CnAShareStampDutyRuleBook` types only when the exact basis and scope can be enforced by those policies.

The identities are deliberately separate:

1. **closure identity** binds all evidence, documentary/economic lineages, candidate dispositions, scope, basis, and cutoffs;
2. **projection identity** binds closure identity, selected revisions, finite target, algorithm, scope, basis, and resulting RuleBook hashes;
3. **execution RuleBook identity** binds only canonical target economics and the stable economic-authority refs consumed by existing fee/tax policies.

Any new evidence changes closure, projection, declaration, event, stream, manifest, and publication identities. Existing finite RuleBook bytes/hashes change only when canonical target economics change. Closure-only evidence may therefore produce a new projection/publication with byte-identical RuleBooks; a target-affecting correction must change the affected RuleBook bytes/hash. Closure or projection hashes must not be inserted into economic source refs or generated charge-rule IDs merely to force execution identity changes.

## Availability and historical claims

The preserved economic target is:

```text
UTC:           [2026-07-05T16:00:00Z, 2026-07-30T16:00:00Z)
Asia/Shanghai: [2026-07-06 00:00:00+08:00, 2026-07-31 00:00:00+08:00)
```

The old `2026-07-20T10:00:00Z` time remains an immutable historical fact named only `historical_profile_composed_at`. It is not an evidence availability or record cutoff.

Every F1-F3 body and validation path enforces exactly:

```text
target_to_exclusive <= official_record_as_of <= closure_evidence_available_at
```

- **As-of closure** selects only official revisions published or recorded no later than `official_record_as_of`.
- **Retrospective closure** requires `official_record_as_of` at or after target end and uses captures/receipts available no later than `closure_evidence_available_at`.
- F1 uses retrospective closure. Its failure/result evaluation time is an explicit immutable closure cutoff supplied by the artifact, never wall clock or inferred file/retrieval time.
- An official revision recorded after `official_record_as_of`, or a capture/receipt available after `closure_evidence_available_at`, is not selectable.
- Any violation, including substitution of `historical_profile_composed_at` for either cutoff, is `CUTOFF_INVALID`.
- Later evidence or corrections create new additive identities. Prior artifacts remain immutable and truthful for their own cutoffs.

## F1 — capture and verify real closure evidence

### Scope

The F1/F2 success envelope is exactly the full domain enforceable by `CnAShareCashFeeRuleQuery` for the preserved target:

```text
venue_id: XSHE
instrument_type: InstrumentType.EQUITY
quote_currency_id: CNY
settlement_currency_id: CNY
trade_mechanism: AUCTION
board_scope: all boards (query-indistinguishable)
access_channel_scope: all access channels (query-indistinguishable)
basis: trade_notional
```

Only these ordered lineages are in scope:

1. `exchange_handling`;
2. `securities_regulatory`;
3. `stock_transfer`;
4. `stamp_duty`.

The query cannot distinguish domestic access from Stock Connect or distinguish boards. F1 must therefore close every fee/tax difference applicable anywhere in the envelope, including Stock Connect. Domestic-only, Main-Board-only, or Stock-Connect-excluding evidence is an explicit current limitation and cannot pass F1. F2 returns `UNSUPPORTED_SCOPE` before RuleBook construction for any narrower authority.

A separately approved execution-enforced discriminator contract could permit narrower board/access authority. It is outside this plan and cannot be assumed by F1-F3.

### Required proof

For every lineage, capture and verify:

1. exact official predecessor authority and every semantic field used by economics: competent issuer, official act, authoritative `effective_from`, rate, `trade_notional` basis, buy/sell applicability, XSHE, `InstrumentType.EQUITY`, CNY quote/settlement, `AUCTION`, all boards, and all query-indistinguishable access channels;
2. every documentary representation and exact `corrects_revision_id` chain for each official act;
3. every selected complete economic state and exact `economic_predecessor_revision_id` chain across official acts;
4. an official endpoint table, validity record, or complete historical register whose record state is at or after target end;
5. every competent-authority successor/correction index or channel through `official_record_as_of`;
6. complete pagination/cursor/range termination and an ordered inventory of candidate entries;
7. exact official bytes for every result-affecting predecessor, endpoint, successor, correction, and index representation;
8. deterministic disposition of every candidate as no effect, outside scope, before target/already in chain, after target, documentary correction without economic change, target-affecting correction/successor, repeal without replacement, or unresolved;
9. terminal documentary representation selection per official act, followed by a gap-free, non-overlapping, conflict-free economic target conclusion per lineage.

A current endpoint alone, a search-engine result, an undocumented keyword search, or “no successor found” is insufficient. Regulatory fee closure must cover both controlling rate authority and XSHE bilateral investor-collection applicability. Stamp-duty closure must cover both the statutory seller-side basis and the half-collection act.

Exact bytes, source-specific receipts, redirects, headers, content encoding, rendered/attachment hashes, extraction hashes, and pagination termination are sufficient acquisition controls. They are not a mandatory universal transport schema: freeze only fields required to prove the selected source representation and closure claim.

### Canonical closure artifact

Freeze one canonical JSON body with this exact top-level field order and schema version:

```text
{
  type: "cn_a_share_official_rule_successor_closure",
  schema_version: 1,
  closure_key,
  closure_version,
  semantics_id: "effective-until-authoritatively-superseded.v1",
  closure_kind: "retrospective",
  baseline_binding,
  target_scope,
  historical_profile_composed_at,
  closure_evidence_available_at,
  official_record_as_of,
  components,
  qualification,
  limitations
}
```

`baseline_binding` binds the immutable v1 declaration hash, publication manifest hash, profile request hash, market-profile digest, component-manifest hash, source-manifest hash, exact target, and existing blocker result.

`target_scope` freezes XSHE, `InstrumentType.EQUITY`, CNY quote and settlement, `AUCTION`, all boards, all query-indistinguishable access channels, exact `trade_notional` basis, and target bounds. The exact invariant is `target_to_exclusive <= official_record_as_of <= closure_evidence_available_at`. Each selected official revision is published/recorded by `official_record_as_of`; every source capture and receipt used is available by `closure_evidence_available_at`.

`components` is a four-item tuple in the lineage order above. Each component body is exact:

```text
{
  lineage_key,
  documentary_representations,
  selected_documentary_revision_ids,
  selected_economic_state_hashes,
  predecessor_source_refs,
  endpoint_source_refs,
  successor_index_refs,
  candidate_disposition_refs,
  terminal_economic_revision_id,
  terminal_economic_state_hash,
  conclusion
}
```

Each documentary representation binds `official_act_id`, `revision_id`, `corrects_revision_id`, `official_recorded_at`, representation source refs, and representation hash. Selected economic states additionally bind `economic_predecessor_revision_id`, authoritative `effective_from`, rate, basis, side applicability, and full scope. Closure selects exactly one documentary terminal per official act before evaluating the economic chain.

`economic_state_hash` is a projection/provenance identity canonical over official act identity, lineage, normalized economic predecessor act, authoritative effective time, rate, basis, side applicability, and full scope. It excludes documentary revision IDs and acquisition metadata. Separately, each finite target segment derives a `target_economic_semantics_hash` only from lineage, clipped interval, rate, basis, side applicability, and full scope. It excludes official act, revision, predecessor, capture/receipt, closure, and projection identities. Execution source refs derive only from that target-economic hash. Therefore any evidence or authority-lineage change with identical target economics changes closure/projection identities but not execution RuleBook bytes.

Allowed conclusions are `closed_unchanged` and `closed_with_successor_bands`. A later documentary correction with no canonical target-economic change may remain `closed_unchanged`; a correction that changes any target segment is `closed_with_successor_bands`. Repeal without a complete replacement, unresolved documentary/economic fork, scope/effective-time conflict, incomplete index coverage, gap, or overlap fails F1.

`qualification` may set only dimension-scoped official successor closure true. Provider authority, provider completeness, rule coverage, decision grade, live use, and deployment remain false.

`closure_hash = canonical_sha256(body)`. Caller-supplied hashes are never trusted where the body can be reconstructed.

### F1 canonical failures

Failure precedence is exact; ties use the lineage order above and then canonical source/candidate identity order:

1. `SCOPE_MISMATCH`;
2. `CUTOFF_INVALID`;
3. `PREDECESSOR_EVIDENCE_MISSING`;
4. `ENDPOINT_EVIDENCE_MISSING`;
5. `AUTHORITY_SCOPE_GAP`;
6. `SUCCESSOR_INDEX_INCOMPLETE`;
7. `SUCCESSOR_CANDIDATE_UNRESOLVED`;
8. `REVISION_CHAIN_CONFLICT`;
9. `TARGET_COVERAGE_GAP`;
10. `TARGET_COVERAGE_OVERLAP`.

A failure body is canonical JSON:

```text
{
  type: "cn_a_share_official_rule_successor_closure_failure",
  schema_version: 1,
  closure_key,
  code,
  lineage_key,
  subject_ids,
  evidence_available_at
}
```

`lineage_key` is exactly `rule_closure` for `SCOPE_MISMATCH` and `CUTOFF_INVALID`; every other F1 failure uses the first affected charge lineage, falling back to `rule_closure` only when no lineage can be identified. `subject_ids` is exactly `(code, lineage_key, closure_key, *canonically_sorted_offending_ids)`. Offending IDs are unique and sorted by canonical bytes. `evidence_available_at` is exactly the explicit immutable `closure_evidence_available_at` supplied to the attempted closure evaluation; it is never inferred from captures, filesystem metadata, process time, or wall clock. Every cutoff/availability invariant violation maps to `CUTOFF_INVALID`.

Failure is atomic: no successful closure artifact, derived RuleBook, declaration, or publication may be emitted.

### F1 pass gate

F1 passes only after exact captures, normalized source identities, closure body/hash, failure-free reconstruction, and independent source/closure review pass. Until then no production projector, runtime/profile composer, v2 fixture, or v2 publication is authorized.

## F2 — pure source authority to finite execution RuleBooks

**Blocked by F1.** Implement only if the accepted F1 artifact proves real closure and a projection function is still needed.

### Precise seam

Add one concrete module beside the existing Kernel A-share fee/tax types:

```text
packages/trading-kernel/src/crypto_quant_trading/profiles/cn_a_share/effective_fee_tax_rules.py
```

It owns exactly one public operation:

```python
project_cn_a_share_effective_fee_tax_rules(
    request: CnAShareEffectiveFeeTaxProjectionRequest,
    /,
) -> CnAShareEffectiveFeeTaxProjection | CnAShareEffectiveFeeTaxProjectionFailure
```

The module may import `commission_tax` and domain value types. It imports no Builder, Runtime, provider, repository, filesystem, network, database, process, or wall clock. It performs no I/O. No class-based projector, Protocol, interface, registry, resolver, factory, composer, adapter framework, DSL, callback, cache, or plug-in is added.

If exported, concrete types and the function are exported only from `crypto_quant_trading.profiles.cn_a_share`, not the global `crypto_quant_trading` root.

### Source revision body

One normalized revision is one documentary representation of a complete charge state:

```text
{
  type: "cn_a_share_official_charge_rule_revision",
  schema_version: 1,
  official_act_id,
  revision_id,
  corrects_revision_id,
  economic_predecessor_revision_id,
  lineage_key,
  venue_id,
  instrument_type,
  quote_currency_id,
  settlement_currency_id,
  trade_mechanism,
  board_scope,
  access_channel_scope,
  basis,
  effective_from,
  official_recorded_at,
  rate,
  applies_to_buy,
  applies_to_sell,
  source_refs
}
```

`corrects_revision_id` is `None` only for the first documentary representation of one `official_act_id`; otherwise it names the immediately corrected representation of that same act. `economic_predecessor_revision_id` names the selected complete economic state from the preceding official act, or `None` for the root. It never substitutes for documentary correction.

The accepted exact scope is XSHE, `InstrumentType.EQUITY`, CNY quote and settlement, `AUCTION`, `board_scope="all_boards"`, `access_channel_scope="all_query_indistinguishable_access_channels"`, and `basis="trade_notional"`. The first three lineages are bilateral; stamp duty is seller-only. `Rate.basis` remains `fee_fraction` and is distinct from calculation `basis`. Source refs reuse `CnAShareFeeRuleSourceRef` for documentary authority; execution Bands use deterministic semantic refs derived only from canonical finite target economics, not official-act, revision, predecessor, closure, capture, or receipt identity.

At `official_record_as_of`, group by `official_act_id`, select one terminal `corrects_revision_id` chain member, normalize economic predecessor links to selected terminals, then sort economic states by authoritative `effective_from`. A retroactive correction may move a boundary earlier than its publication or its prior representation and does not fail solely for that ordering. No caller-supplied end exists: each end is the next selected economic state's effective time or the finite target end. Unresolved correction/economic forks, cycles, equal-time conflicting states, gaps, overlaps, repeal without replacement, and incomplete replacement fail closed.

### Projection request and result

The canonical request body is exact:

```text
{
  type: "cn_a_share_effective_fee_tax_projection_request",
  schema_version: 1,
  request_key,
  venue_id,
  instrument_type,
  quote_currency_id,
  settlement_currency_id,
  trade_mechanism,
  board_scope,
  access_channel_scope,
  basis,
  target_from,
  target_to_exclusive,
  official_record_as_of,
  closure_evidence_available_at,
  closure_body,
  closure_hash,
  revisions
}
```

The request and its hash bind the exact four lineages and full applicability scope. It requires a finite non-empty target and exactly `target_to_exclusive <= official_record_as_of <= closure_evidence_available_at`. Every selected revision must have `official_recorded_at <= official_record_as_of`; every bound capture/receipt must be available by `closure_evidence_available_at`. Violations are `CUTOFF_INVALID`.

Before constructing any Band, projection rejects unsupported basis or scope. In v1, `basis` must be `trade_notional`, and scope must equal the complete query-enforceable envelope above. Domestic-only, Main-Board-only, or Stock-Connect-excluding evidence is `UNSUPPORTED_SCOPE`; it cannot yield a generally reusable RuleBook. Success requires closure of any Stock Connect or other access-channel fee/tax difference within the envelope.

Projection first selects terminal documentary representations, then orders selected economic states by `effective_from`, derives boundaries, clips each lineage to the target, unions the three fee-lineage boundaries, resolves exactly one state per segment, and constructs existing finite Bands and RuleBooks. Adjacent Bands may coalesce only when every canonical target-economic field and stable economic-authority ref is identical.

Execution RuleBook identities are new lineages:

```text
equity.cn_a_share.cash.market-fees.effective-until-superseded.v1
equity.cn_a_share.cash.stamp-duty.effective-until-superseded.v1
```

Both use `rule_book_version=1`. Closure-only evidence, documentary correction, or a new official act with identical target economics leaves these RuleBook canonical bytes and hashes unchanged. Only a changed target interval, rate, side, basis, or supported scope changes the affected RuleBook hash. Any new evidence still changes projection/declaration/publication identities. A projection semantic/schema change increments the algorithm/type/key version.

The canonical result body is exact:

```text
{
  type: "cn_a_share_effective_fee_tax_projection",
  schema_version: 1,
  algorithm_id: "cn-a-share-effective-until-superseded-fee-tax-projection-v1",
  request_hash,
  closure_hash,
  venue_id,
  instrument_type,
  quote_currency_id,
  settlement_currency_id,
  trade_mechanism,
  board_scope,
  access_channel_scope,
  basis,
  target_from,
  target_to_exclusive,
  official_record_as_of,
  closure_evidence_available_at,
  selected_documentary_revision_hashes,
  selected_economic_state_hashes,
  market_fee_rule_book,
  market_fee_rule_book_hash,
  stamp_duty_rule_book,
  stamp_duty_rule_book_hash
}
```

`projection_hash = canonical_sha256(result body)`. Selected hashes use the four-lineage order and make every evidence change visible in projection identity. Closure/projection/documentary hashes remain outside existing RuleBook and generated fee-rule canonical preimages; RuleBook refs bind stable canonical economic states.

### F2 failures

Exact first-failure precedence:

1. `UNSUPPORTED_SCOPE`;
2. `UNSUPPORTED_BASIS`;
3. `CUTOFF_INVALID`;
4. `CLOSURE_BINDING_MISMATCH`;
5. `DOCUMENTARY_CORRECTION_MISMATCH`;
6. `ECONOMIC_SUCCESSION_MISMATCH`;
7. `SUCCESSOR_TERMINAL_MISMATCH`;
8. `UNSUPPORTED_REVISION_DISPOSITION`;
9. `ECONOMIC_TIMELINE_CONFLICT`;
10. `COVERAGE_GAP`;
11. `PROJECTED_OVERLAP`.

The canonical failure body contains `type`, `schema_version`, full request, `request_hash`, `code`, `lineage_key`, and `subject_ids`; its constructor recomputes the first applicable failure. `lineage_key` is exactly `fee_tax_projection` for `UNSUPPORTED_SCOPE`, `UNSUPPORTED_BASIS`, `CUTOFF_INVALID`, and `CLOSURE_BINDING_MISMATCH`; every later code uses the first affected charge lineage. `subject_ids` is exactly `(code, lineage_key, request_key, *canonically_sorted_offending_ids)`, with unique offending IDs sorted by canonical bytes. All record/capture/historical-time invariant violations are `CUTOFF_INVALID`. Malformed exact types, noncanonical text/hash, invalid rates, and empty targets are constructor errors. Failure returns no partial RuleBook.

## F3 — additive five-dimension declaration and G12C/D publication v2

**Blocked by F1 and F2.** Do not add a Runtime/profile composer. Do not replace or recompute the G08H v1 profile under the same key/version.

### Declaration

Add one new canonical declaration lineage:

```text
{
  type: "cn_a_share_official_rule_publication_declaration",
  schema_version: 1,
  publication_version: 2,
  authority_build,
  baseline_profile_binding,
  continuity_semantics,
  target_coverage,
  retrospective_availability,
  closure_binding,
  projection_binding,
  required_dimensions,
  authorities,
  qualification
}
```

Rules:

- `baseline_profile_binding` preserves the immutable G08H/v1 identities and labels them historical context, not proof that the old profile contained projected fee/tax RuleBooks;
- `continuity_semantics` is exactly `effective_until_authoritatively_superseded`;
- `retrospective_availability` contains fields named exactly `historical_profile_composed_at`, `official_record_as_of`, and `closure_evidence_available_at`, and enforces `target_to_exclusive <= official_record_as_of <= closure_evidence_available_at`;
- `closure_binding` contains the closure key/version/hash, full scope/basis, and ordered terminal documentary/economic hashes;
- `projection_binding` contains algorithm ID, projection hash, full scope/basis, and both execution RuleBook hashes;
- `required_dimensions` is exactly `calendar`, `order_rules`, `market_fees`, `stamp_duty`, `corporate_action_entitlements` in that order;
- Calendar, order-rule, and corporate-action canonical bodies/hashes are reused byte-for-byte from v1;
- market-fee and stamp-duty bodies are the F2 finite projections;
- provider, decision-grade, live, and deployment flags remain false; `rule_coverage_qualified` remains false until G12H reports success.

### Builder publication boundary

Add one internal Builder module only after the declaration fixture passes:

```text
packages/market-bundle-builder/src/crypto_quant_bundle_builder/cn_a_share_official_rule_bundle.py
```

It contains one positional-only function:

```python
project_cn_a_share_official_rule_authority_events_v2(
    declaration: Mapping[str, object],
    /,
) -> tuple[MarketEvent, ...]
```

The function canonical-rebuilds and hash-pins the exact declaration, emits exactly five events atomically in required-dimension order, and uses v2 capability/stream/event/bundle identities. Event `available_time` is exactly `closure_evidence_available_at`. Any new evidence changes declaration, event, stream, manifest, retention, Bundle, and publication identities even when projected RuleBook bytes are unchanged.

Builder production imports neither Trading Kernel nor Runtime. It consumes already-canonical authority bodies and does not reconstruct economics. The function is not exported from `crypto_quant_bundle_builder.__init__`. No generic publication framework is added.

Publish through unchanged G12C validation and G12D idempotent publication. Repeated publication must return identical manifest, event, stream, retention, and Bundle identities.

## G12H analyzer RED after F3

Only after F3 passes may RED tests freeze the existing pure atomic analyzer contract. The intended module is one concrete Builder module, `rule_coverage.py`, with no provider lookup, economic evaluator, Runtime/Kernel import, registry, or root export.

The analyzer consumes only the explicit v2 declaration and published manifest/events. It does not parse official notices, rerun F2 economics, discover dimensions from `ProfilePortType`, or enumerate Kernel classes.

### Canonical success and failure

`RuleCoverageReport` canonical body fields are:

```text
type, schema_version, declaration_hash, authority_build_hash,
bundle_manifest_hash, target_coverage, applicability_scope, basis,
historical_profile_composed_at, official_record_as_of,
closure_evidence_available_at, closure_hash, projection_hash,
required_dimensions, dimension_coverage
```

`dimension_coverage` uses required-dimension order and binds each authority hash/body hash plus exact finite intersection. `report_hash` is derived and excluded from its own preimage.

`RuleCoverageFailure` canonical body fields are:

```text
type, schema_version, declaration_hash, bundle_manifest_hash,
code, dimension, subject_ids
```

The function returns exactly one report or one failure, never partial dimension success.

Exact failure precedence remains:

1. `invalid_input`;
2. `bundle_declaration_mismatch`;
3. `missing_required_dimension`;
4. `coverage_gap`;
5. `coverage_overlap`;
6. `source_identity_mismatch`.

Within a code, the five-dimension order decides first failure. Zero declared dimensions is `invalid_input`. Closure/projection/RuleBook/body hash mismatch is `source_identity_mismatch`; malformed retrospective availability is `invalid_input`. Subject IDs are `(code, dimension-or-rule_coverage, declaration_hash, manifest_hash-or-missing)`.

### RED matrix

- v1 declaration remains `coverage_gap / market_fees` and all accepted bytes remain exact;
- empty, missing, extra, duplicate, or reordered dimensions fail deterministically;
- declaration/Bundle/profile-context/target/scope/basis mismatch fails atomically;
- closure, projection, authority-body, source, event, or manifest mutation changes all additive identities;
- closure-only evidence change yields new closure/projection/declaration/publication hashes while both finite RuleBook bytes/hashes remain exact;
- a post-target documentary correction with unchanged target economics has the same RuleBooks but new additive identities;
- a post-target correction that retroactively changes a target segment is selected at cutoff, splits/replaces the affected target Band, and changes the affected RuleBook hash;
- documentary terminals are selected per official act before economic states are ordered by `effective_from`; publication order does not cause rejection;
- unresolved documentary/economic fork, gap, overlap, equal-time conflict, or contradictory applicability fails closed;
- exact cutoff equality passes; target end after record cutoff, record cutoff after closure evidence availability, selected official revision after record cutoff, capture/receipt after evidence cutoff, and historical composition time substitution all fail `CUTOFF_INVALID`;
- unsupported `basis`, domestic-only, board-limited, or Stock-Connect-excluding applicability fails before RuleBook construction and returns no partial output;
- gap at target start/middle/end and overlap at every boundary fail in dimension order;
- exact half-open adjacency passes; target-end equality is not overlap;
- calendar local-date and UTC dimensions preserve their declared domains;
- market-fee applicability keeps handling/regulatory/transfer source tuples distinct;
- repeated analysis yields byte-identical report/failure hashes;
- provider, decision-grade, live, and deployment flags cannot become true;
- no Runtime/Kernel import, Builder root export, generic rule model, or second economic engine appears.

## Validation by phase

### F1

- independently verify official domains, bytes, receipts, correction/succession indexes, range/termination, candidate inventory, and dispositions;
- reconstruct every canonical documentary representation, economic state, candidate, component, and closure hash twice;
- assert `target_to_exclusive <= official_record_as_of <= closure_evidence_available_at`, official-record selection, capture/receipt availability, and explicit immutable evaluation cutoff;
- test closure-only evidence and post-target target-affecting correction cases;
- run gitleaks against captured artifacts and repository diff.

### F2

- focused pure tests for documentary terminal selection, economic predecessor normalization, publication-order independence, retroactive target correction, in-target successor split, after-target successor, unresolved repeal/fork/cycle/conflict, every cutoff violation, target clipping, gap/overlap, canonical hashes, forged constructors, and no partial output;
- prove closure-only evidence changes projection/publication identity but not RuleBook bytes, while target-affecting correction changes the affected RuleBook hash;
- reject unsupported basis and any domestic-only, board-limited, or access-channel-limited scope before RuleBook construction;
- rerun existing G08E tests and accepted fixture hashes unchanged;
- architecture assertion for the one concrete Kernel seam and forbidden imports.

### F3

- exact v2 declaration/publication golden tests, G12C validation, G12D first/repeated publish, mutation matrix, and five-event order;
- architecture assertion for one internal Builder function, no Kernel/Runtime/provider imports, and no root export;
- rerun v1 projector/blocker/golden tests and byte hashes unchanged.

### G12H RED

Freeze RED only after F3 evidence is immutable. Do not implement GREEN in the same evidence/publication change unless separately authorized.

Every phase ends with focused pytest, import-boundary checks, canonical source assertions, `uv lock --check`, `git diff --check`, gitleaks, clean status review, and independent review.

## Nonclaims and prohibited scope

This plan does not claim provider/archive completeness, universal broker commission, minimum commission, bundled fees, rebates, official rounding, block trading, after-hours trading, B shares, funds, bonds, margin/short, non-CNY scope, account-statement parity, broader Stock Connect trading qualification, live/current qualification, decision grade, or deployment authorization. Current evidence is domestic/Main-focused and does not close Stock Connect or every other query-indistinguishable access-channel fee/tax difference, so F1 remains blocked.

Do not modify existing G08E/G08H types or fixtures; existing G12C/D v1 fixtures/projector; the blocker test; registries; shared Acceptance Matrix; plan README; or root exports. Do not merge or push as part of this plan freeze.
