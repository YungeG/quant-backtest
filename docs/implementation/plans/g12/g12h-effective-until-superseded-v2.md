---
id: G12H-EFFECTIVE-UNTIL-SUPERSEDED-V2
proposed_readiness: READY_FOR_F1_AUTHORITY_CLOSURE
registry_status: SEE_PARENT_ACCEPTANCE_MATRIX
owner: official-source acquisition + trading-kernel projection + market-bundle-builder publication
produces:
  - official-rule successor-closure artifact v1
  - finite target-scoped fee/tax RuleBooks
  - additive five-dimension declaration and G12C/D publication v2
consumes:
  - exact official predecessor, endpoint, and successor-index evidence
  - immutable G08E/G08H and G12C/D v1 identities
  - ADR 0004 effective-until-authoritatively-superseded semantics
  - ADR 0005 execution access-route and fee-product-class semantics
  - G08E route/product fee v2 parent-Matrix PASSED registry fact
depends_on:
  contract: [G08E, G08H, G08E-ROUTE-PRODUCT-FEE-V2C, G12C, G12D]
  evidence: [] # F1 acquires raw evidence after V2C parent-registry PASSED
  write_conflict: [kernel-cn-a-share-fee-tax, builder-rule-publication, acceptance-registry]
fan_out: [G12H, G12L-*, G12M-*]
---

# G12H Effective-Until-Authoritatively-Superseded v2

## Status and authority

The parent [Acceptance Matrix](../../acceptance-matrix.md) is the sole current Gate-status authority and records G08E V2A/V2B/V2C `PASSED`. Scoped F1 authority-closure acquisition is therefore ready only for execution-enforced `DOMESTIC + ORDINARY_A_SHARE`. V2C acceptance uses finite XSHE compatibility economics and requires no G12H closure artifact, so the DAG is not circular. F2 projection, F3 publication, analyzer RED, and qualification changes remain unauthorized until F1 closes its required predecessor/endpoint/successor evidence. No default, inference, silent Stock Connect/product exclusion, or interchangeable v2 RuleBook pairing is permitted.

Accepted semantics: [ADR 0004](../../../adr/0004-official-rules-effective-until-authoritatively-superseded.md) and [ADR 0005](../../../adr/0005-cn-a-share-fees-require-access-route-and-product-class.md).

Evidence baseline:

- [G12H five-dimension blocker](../../../research/g12h-five-dimension-target-coverage-blocker-v1.md);
- [G12H rule-coverage analysis](../../../research/g12h-rule-coverage.md);
- [XSHE July-2026 fee/tax source research](../../../research/g12h-xshe-july-2026-fee-tax-authority-primary-sources.md);
- [F1 full-envelope access/product blocker](../../../research/g12h-xshe-july-2026-full-envelope-successor-closure-f1.md).

The existing v1 declaration still deterministically fails `COVERAGE_GAP / market_fees`. No existing PASSED G08E, G08H, G12C/D, fixture, hash, event, manifest, test, or publication byte may change.

## Frozen decision

A scoped official rule revision is economically effective from its authoritative start until a competent authority makes an authoritative successor effective. Documentary correction and economic succession are independent: `corrects_revision_id` links representations of the same official act, while `economic_predecessor_revision_id` links complete economic states across official acts. At cutoff, closure selects the terminal documentary representation of each act, then orders selected economic states by authoritative `effective_from`; publication, capture, and tuple order never decide economic order. Retroactive correction is allowed, including one recorded after target end that changes a target segment. Unresolved documentary/economic forks, gaps, overlaps, or conflicts fail closed.

Source-law continuity is not an execution interval: a successful closure is projected to one finite target and materialized with the additive finite `CnAShareMarketFeeBandV2`, `CnAShareStampDutyBandV2`, `CnAShareMarketFeeRuleBookV2`, and `CnAShareStampDutyRuleBookV2` types only after the passed route/product contract makes the exact basis and scope execution-enforceable. Existing v1 types remain byte-identical historical authority and are not July-2026 output types.

The identities are deliberately separate:

1. **closure identity** binds all evidence, documentary/economic lineages, candidate dispositions, scope, basis, and cutoffs;
2. **projection identity** binds closure identity, selected revisions, finite target, algorithm, scope, basis, and resulting RuleBook hashes;
3. **execution RuleBook identity** binds only canonical target economics and nonempty stable economic-authority refs; [G08E-V2B](../g08/g08e-route-product-fee-v2-runtime-binding.md), after V2A passes, owns later Runtime selection and profile/build semantic binding without changing this economic identity.

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

F1 itself owns acquisition, immutable capture, normalization, and verification of all raw XSHE successor/correction/endpoint evidence. Completed closure is therefore an F1 output, not a pre-start dependency; the only pre-start gate is the passed V2C parent-registry fact.

### Scope

The parent Acceptance Matrix records [G08E-V2C acceptance](../g08/g08e-route-product-fee-v2-acceptance.md) `PASSED`; scoped F1 authority-closure acquisition is authorized. The F1/F2 success envelope is exactly the execution-enforceable scope below:

```text
execution_access_route: DOMESTIC
fee_product_class: ORDINARY_A_SHARE
venue_id: XSHE
instrument_type: InstrumentType.EQUITY
quote_currency_id: CNY
settlement_currency_id: CNY
trade_mechanism: AUCTION
board_scope: all boards admitted by the bound profile
basis: trade_notional
```

Only these ordered lineages are in scope:

1. `exchange_handling`;
2. `securities_regulatory`;
3. `chinaclear_transfer`;
4. `hkscc_transfer`;
5. `stamp_duty`.

`exchange_handling` is the official-source lineage and maps only to the v2 generated charge key `handling`; `securities_regulatory`, `chinaclear_transfer`, `hkscc_transfer`, and `stamp_duty` map to identically named v2 keys. `hkscc_transfer` is retained as an explicit route-applicability lineage and must close as not applicable for `DOMESTIC`; it is never blended with `chinaclear_transfer`. Northbound, preferred-stock, and ETF evidence/books are outside this G12H increment and cannot fall back to domestic ordinary economics. Board remains constrained by the immutable bound profile; no symbol or stable-key inference is allowed.

### Required proof

For every lineage, capture and verify:

1. exact official predecessor authority and every semantic field used by economics: competent issuer, official act, authoritative `effective_from`, rate or explicit not-applicability, `trade_notional` basis, buy/sell applicability, XSHE, `InstrumentType.EQUITY`, CNY quote/settlement, `AUCTION`, all profile-admitted boards, `execution_access_route=DOMESTIC`, and `fee_product_class=ORDINARY_A_SHARE`;
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

`baseline_binding` binds the immutable v1 declaration hash, publication manifest hash, profile request hash, market-profile digest, component-manifest hash, source-manifest hash, exact target, existing blocker result, and the parent Acceptance Matrix G08E-V2C `PASSED` registry fact together with V2C acceptance-closure final source commit and protected fixture/artifact hashes. It does not prescribe V2B profile/build leaf identities or require future G12H closure books for G08E acceptance. V1 identities remain historical context, not route/product execution authority.

`target_scope` freezes XSHE, `InstrumentType.EQUITY`, CNY quote and settlement, `AUCTION`, all profile-admitted boards, `execution_access_route=DOMESTIC`, `fee_product_class=ORDINARY_A_SHARE`, exact `trade_notional` basis, and target bounds. The exact invariant is `target_to_exclusive <= official_record_as_of <= closure_evidence_available_at`. Each selected official revision is published/recorded by `official_record_as_of`; every source capture and receipt used is available by `closure_evidence_available_at`.

`components` is a five-item tuple in the lineage order above. Each component body is exact:

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

Each documentary representation binds `official_act_id`, `revision_id`, `corrects_revision_id`, `official_recorded_at`, representation source refs, and representation hash. Selected economic states additionally bind `economic_predecessor_revision_id`, authoritative `effective_from`, applies state, rate, basis, side applicability, execution access route, fee product class, and full scope. Closure selects exactly one documentary terminal per official act before evaluating the economic chain.

`economic_state_hash` is a projection/provenance identity canonical over official act identity, lineage, normalized economic predecessor act, authoritative effective time, applies state, rate, basis, side applicability, execution access route, fee product class, and full scope. It excludes documentary revision IDs and acquisition metadata. Separately, each finite target segment derives a `target_economic_semantics_hash` only from lineage, clipped interval, applies state, rate, basis, side applicability, execution access route, fee product class, and full scope. It excludes official act, revision, predecessor, capture/receipt, closure, and projection identities. Execution source refs derive only from that target-economic hash. Therefore any evidence or authority-lineage change with identical target economics changes closure/projection identities but not execution RuleBook bytes.

Allowed conclusions are `closed_unchanged`, `closed_with_successor_bands`, and `closed_not_applicable`. Only `hkscc_transfer` may use `closed_not_applicable`, and only with official route-applicability evidence for `DOMESTIC`. A later documentary correction with no canonical target-economic change may remain `closed_unchanged`; a correction that changes any target segment is `closed_with_successor_bands`. Repeal without a complete replacement, unresolved documentary/economic fork, scope/effective-time conflict, incomplete index coverage, gap, or overlap fails F1.

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

F1 cannot start until the parent Acceptance Matrix records G08E-V2C acceptance `PASSED`; V2A or V2B alone cannot start it. V2C uses only the finite XSHE compatibility projection and is not an F1 output or prerequisite. Once started, F1 passes only after exact captures, normalized source identities, closure body/hash, failure-free reconstruction, and independent source/closure review pass. Until then no G12H projector, declaration fixture, publication, or analyzer RED is authorized.

## F2 — pure source authority to finite execution RuleBooks

**Blocked by F1.** Implement only if the accepted F1 artifact proves real closure and a projection function is still needed.

### Precise seam

Add one concrete module beside the existing Kernel A-share fee/tax types:

```text
packages/trading-kernel/src/crypto_quant_trading/profiles/cn_a_share/effective_fee_tax_rules_v2.py
```

It owns exactly one public operation:

```python
project_cn_a_share_effective_fee_tax_rules_v2(
    request: CnAShareEffectiveFeeTaxProjectionRequestV2,
    /,
) -> CnAShareEffectiveFeeTaxProjectionV2 | CnAShareEffectiveFeeTaxProjectionFailureV2
```

The module may import `commission_tax_v2` and domain value types. It imports no Builder, Runtime, provider, repository, filesystem, network, database, process, or wall clock. It performs no I/O. No class-based projector, Protocol, interface, registry, resolver, factory, composer, adapter framework, DSL, callback, cache, or plug-in is added.

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
  execution_access_route,
  fee_product_class,
  basis,
  effective_from,
  official_recorded_at,
  applies,
  rate,
  applies_to_buy,
  applies_to_sell,
  source_refs
}
```

`corrects_revision_id` is `None` only for the first documentary representation of one `official_act_id`; otherwise it names the immediately corrected representation of that same act. `economic_predecessor_revision_id` names the selected complete economic state from the preceding official act, or `None` for the root. It never substitutes for documentary correction.

The accepted exact scope is XSHE, `InstrumentType.EQUITY`, CNY quote and settlement, `AUCTION`, `board_scope="all_profile_admitted_boards"`, `execution_access_route="domestic"`, `fee_product_class="ordinary_a_share"`, and `basis="trade_notional"`. Handling, regulatory, and ChinaClear transfer are bilateral; HKSCC transfer is explicitly not applicable for the domestic route; stamp duty is seller-only. `Rate.basis` remains `fee_fraction` and is distinct from calculation `basis`. Every execution Band source-ref tuple is nonempty, canonical-sorted, and duplicate-free. F2 derives each ref deterministically only from canonical finite target economics, including applies state; HKSCC domestic not-applicability has its own nonempty target-economic authority ref, never an empty/provenance-free component. Documentary authority refs reuse `CnAShareFeeRuleSourceRef` and execution refs exclude official-act, revision, predecessor, closure, capture, and receipt identity.

At `official_record_as_of`, group by `official_act_id`, select one terminal `corrects_revision_id` chain member, normalize economic predecessor links to selected terminals, then sort economic states by authoritative `effective_from`. A retroactive correction may move a boundary earlier than its publication or its prior representation and does not fail solely for that ordering. No caller-supplied end exists: each end is the next selected economic state's effective time or the finite target end. Unresolved correction/economic forks, cycles, equal-time conflicting states, gaps, overlaps, repeal without replacement, and incomplete replacement fail closed.

### Projection request and result

The canonical request body is exact:

```text
{
  type: "cn_a_share_effective_fee_tax_projection_request_v2",
  schema_version: 1,
  request_key,
  venue_id,
  instrument_type,
  quote_currency_id,
  settlement_currency_id,
  trade_mechanism,
  board_scope,
  execution_access_route,
  fee_product_class,
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

The request and its hash bind the exact five lineages and full applicability scope. It requires a finite non-empty target and exactly `target_to_exclusive <= official_record_as_of <= closure_evidence_available_at`. Every selected revision must have `official_recorded_at <= official_record_as_of`; every bound capture/receipt must be available by `closure_evidence_available_at`. Violations are `CUTOFF_INVALID`.

Before constructing any Band, projection rejects unsupported basis or scope. `basis` must be `trade_notional`, route/product must be exactly `DOMESTIC + ORDINARY_A_SHARE`, and the remaining scope must equal the execution-enforceable envelope above. Northbound, preferred-stock, ETF, board-limited outside the bound profile, or route/product-omitting evidence is `UNSUPPORTED_SCOPE` and returns no partial RuleBook.

Projection first selects terminal documentary representations, then orders selected economic states by `effective_from`, derives boundaries, clips each lineage to the target, unions the four market-fee lineage boundaries, resolves exactly one state per segment, and constructs additive finite v2 Bands and RuleBooks. It rejects any non-XSHE candidate/source Band before construction. The HKSCC component remains separately represented as not applicable with a nonempty deterministic authority ref; it is never omitted, provenance-free, or merged into ChinaClear. Adjacent Bands may coalesce only when every canonical target-economic field and stable economic-authority ref is identical.

Execution RuleBook identities are new lineages:

```text
equity.cn_a_share.cash.market-fees.domestic.ordinary-a-share.effective-until-superseded.v2
equity.cn_a_share.cash.stamp-duty.domestic.ordinary-a-share.effective-until-superseded.v2
```

Both use `rule_book_version=2` and exact route/product scope. Closure-only evidence, documentary correction, or a new official act with identical target economics leaves these RuleBook canonical bytes and hashes unchanged. Only a changed target interval, rate, side, basis, or supported scope changes the affected RuleBook hash. Any new evidence still changes projection/declaration/publication identities. A projection semantic/schema change increments the algorithm/type/key version.

The canonical result body is exact:

```text
{
  type: "cn_a_share_effective_fee_tax_projection_v2",
  schema_version: 1,
  algorithm_id: "cn-a-share-effective-until-superseded-fee-tax-projection-v2",
  request_hash,
  closure_hash,
  venue_id,
  instrument_type,
  quote_currency_id,
  settlement_currency_id,
  trade_mechanism,
  board_scope,
  execution_access_route,
  fee_product_class,
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

`projection_hash = canonical_sha256(result body)`. Selected hashes use the five-lineage order and make every evidence change visible in projection identity. Closure/projection/documentary hashes remain outside v2 RuleBook and generated fee-rule canonical preimages; RuleBook refs bind stable canonical economic states.

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
- `closure_binding` contains the closure key/version/hash, exact `DOMESTIC + ORDINARY_A_SHARE` scope/basis, and ordered terminal documentary/economic hashes;
- `projection_binding` contains algorithm ID, projection hash, exact route/product/scope/basis, and both execution RuleBook hashes;
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

## G12H RuleCoverage handoff

This effective-until-superseded plan owns successor closure, finite v2 RuleBook projection, and additive publication fan-out only. It does not define, freeze, implement, or produce `RuleCoverageReport` or `RuleCoverageFailure`; those remain solely owned by [G12H Rule Coverage](g12h.md) after its own prerequisites pass. Any analyzer RED/GREEN, fields, failures, and acceptance belong there.

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
- reject unsupported basis, any route other than `DOMESTIC`, any product other than `ORDINARY_A_SHARE`, omitted route/product, and board scope outside the immutable bound profile before RuleBook construction;
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

This plan does not claim provider/archive completeness, universal broker commission, minimum commission, bundled fees, rebates, official rounding, block trading, after-hours trading, B shares, funds, bonds, margin/short, non-CNY scope, account-statement parity, Northbound qualification, preferred-stock qualification, ETF qualification, live/current qualification, decision grade, or deployment authorization. It also excludes non-notional portfolio, instruction, safekeeping, collateral, corporate-action-service, and settlement-message costs. The route/product fee v2 prerequisite is `PASSED`; incomplete domestic ordinary-A-share predecessor/endpoint/successor authority closure remains the active F1 blocker.

Do not modify existing G08E/G08H types or fixtures; existing G12C/D v1 fixtures/projector; the blocker test; registries; shared Acceptance Matrix; plan README; or root exports. Do not merge or push as part of this plan freeze.
