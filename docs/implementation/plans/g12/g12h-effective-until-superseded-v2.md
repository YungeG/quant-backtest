---
id: G12H-EFFECTIVE-UNTIL-SUPERSEDED-V2
readiness: READY_FOR_F1_EVIDENCE_ACQUISITION_ONLY
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

`READY` for **F1 evidence acquisition only**. F2 projection, F3 declaration/publication, and the G12H analyzer RED contract remain blocked until F1 passes independent evidence review.

Accepted semantics: [ADR 0004](../../../adr/0004-official-rules-effective-until-authoritatively-superseded.md).

Evidence baseline:

- [G12H five-dimension blocker](../../../research/g12h-five-dimension-target-coverage-blocker-v1.md);
- [G12H rule-coverage analysis](../../../research/g12h-rule-coverage.md);
- [XSHE July-2026 fee/tax source research](../../../research/g12h-xshe-july-2026-fee-tax-authority-primary-sources.md).

The existing v1 declaration still deterministically fails `COVERAGE_GAP / market_fees`. No existing PASSED G08E, G08H, G12C/D, fixture, hash, event, manifest, test, or publication byte may change.

## Frozen decision

A scoped official rule revision is economically effective from its authoritative start until a competent authority makes an authoritative successor effective. Source-law continuity is not an execution interval: a successful closure is projected to one finite target and materialized with the existing finite `CnAShareMarketFeeBand`, `CnAShareStampDutyBand`, `CnAShareMarketFeeRuleBook`, and `CnAShareStampDutyRuleBook` types.

The identities are deliberately separate:

1. **closure identity** binds predecessor evidence, endpoint evidence, successor indexes, candidate dispositions, scope, and official-record cutoff;
2. **projection identity** binds closure identity, selected revisions, finite target, algorithm, and resulting RuleBook hashes;
3. **execution RuleBook identity** binds only the finite economic Bands consumed by existing fee/tax policies.

Equal RuleBook hashes do not imply equal closure/projection provenance. Closure or projection hashes must not be inserted into generated economic charge-rule IDs merely to force them to differ.

## Availability and historical claims

The preserved economic target is:

```text
UTC:           [2026-07-05T16:00:00Z, 2026-07-30T16:00:00Z)
Asia/Shanghai: [2026-07-06 00:00:00+08:00, 2026-07-31 00:00:00+08:00)
```

The old `2026-07-20T10:00:00Z` composition/availability instant remains an immutable historical fact. Later evidence is never represented as available then.

- **As-of closure** states the terminal authoritative record visible at its declared cutoff. Projection beyond that cutoff is only a point-in-time belief under the accepted semantics, not retrospectively final history.
- **Retrospective closure** uses evidence actually available after target end and a record cutoff at or after target end to establish the target history as of that later cutoff.
- F1 uses retrospective closure. Its new publication availability is the actual closure-evidence availability time, not the old composition instant.
- A later official retroactive correction or newly discovered successor produces new closure, projection, RuleBook, declaration, and publication identities. Prior artifacts remain immutable and truthfully describe their own cutoffs.

## F1 — capture and verify real closure evidence

### Scope

Only ordinary domestic CNY A-share standard cash-auction executions on XSHE Main Board for the preserved target, and only these ordered lineages:

1. `exchange_handling`;
2. `securities_regulatory`;
3. `stock_transfer`;
4. `stamp_duty`.

### Required proof

For every lineage, capture and verify:

1. exact official predecessor authority and every semantic field used by economics: competent issuer, scope, effective start, rate, basis, buy/sell applicability, venue, and mechanism;
2. an official endpoint table, validity record, or complete historical register whose record state is after target end;
3. every competent-authority successor index/channel capable of amendment, correction, replacement, repeal, suspension, invalidation, or scope change through the declared cutoff;
4. complete pagination/cursor/range termination and an ordered inventory of candidate entries;
5. exact official bytes for every result-affecting predecessor, endpoint, successor, and index representation;
6. deterministic disposition of every candidate as no effect, outside scope, before target/already in chain, after target, non-economic correction, target successor, repeal without replacement, or unresolved;
7. a gap-free, non-overlapping target conclusion and explicit terminal revision for each lineage.

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

`target_scope` freezes Venue, board, instrument class, currency, mechanism, and target bounds. `official_record_as_of` must be at or after target end. `closure_evidence_available_at` must be no earlier than every evidence item used.

`components` is a four-item tuple in the lineage order above. Each component body is exact:

```text
{
  lineage_key,
  predecessor_revision_hashes,
  predecessor_source_refs,
  endpoint_source_refs,
  successor_index_refs,
  candidate_disposition_refs,
  terminal_revision_id,
  terminal_revision_hash,
  conclusion
}
```

Allowed conclusions are `closed_unchanged` and `closed_with_successor_bands`. Repeal without a complete replacement, unresolved scope/effective time, incomplete index coverage, gap, overlap, or conflict fails F1.

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

One normalized revision represents a complete state for one charge lineage:

```text
{
  type: "cn_a_share_official_charge_rule_revision",
  schema_version: 1,
  revision_id,
  supersedes_revision_id,
  lineage_key,
  venue_id,
  trade_mechanism,
  effective_from,
  available_at,
  rate,
  applies_to_buy,
  applies_to_sell,
  source_refs
}
```

The first three lineages are bilateral; stamp duty is seller-only. All rates use `fee_fraction`. Source refs reuse `CnAShareFeeRuleSourceRef`. No caller-supplied end exists: each end is the next authoritative successor effective time or the finite target end for the closure terminal. Same-effective-time corrections select the terminal chain member; decreasing effective time, forks, cycles, unresolved repeal, and incomplete replacement fail closed.

### Projection request and result

The canonical request body is exact:

```text
{
  type: "cn_a_share_effective_fee_tax_projection_request",
  schema_version: 1,
  venue_id,
  trade_mechanism,
  target_from,
  target_to_exclusive,
  closure_evidence_available_at,
  official_record_as_of,
  closure_body,
  closure_hash,
  revisions
}
```

The request requires the exact four lineages, a finite non-empty target, a retrospective record cutoff at or after target end, closure availability no earlier than every supplied revision/evidence item, and constructor-recomputed closure identity.

Projection orders revisions by declared parent chain, derives successor boundaries, clips each lineage to the target, unions the three fee-lineage boundaries, resolves exactly one state per segment, and constructs existing finite Bands and RuleBooks. Adjacent Bands may coalesce only when every economic and source-ref field is identical.

Execution RuleBook identities are new lineages:

```text
equity.cn_a_share.cash.market-fees.effective-until-superseded.v1
equity.cn_a_share.cash.stamp-duty.effective-until-superseded.v1
```

Both use `rule_book_version=1`. New evidence changes content hashes; a projection semantic/schema change increments the algorithm/type/key version.

The canonical result body is exact:

```text
{
  type: "cn_a_share_effective_fee_tax_projection",
  schema_version: 1,
  algorithm_id: "cn-a-share-effective-until-superseded-fee-tax-projection-v1",
  request_hash,
  closure_hash,
  target_from,
  target_to_exclusive,
  official_record_as_of,
  selected_revision_hashes,
  market_fee_rule_book,
  market_fee_rule_book_hash,
  stamp_duty_rule_book,
  stamp_duty_rule_book_hash
}
```

`projection_hash = canonical_sha256(result body)`. The selected revision hashes use the four-lineage order. Closure/projection hashes remain outside the existing RuleBook and generated fee-rule canonical preimages.

### F2 failures

Exact first-failure precedence:

1. `UNSUPPORTED_SCOPE`;
2. `EVIDENCE_NOT_AVAILABLE`;
3. `CLOSURE_BINDING_MISMATCH`;
4. `REVISION_CHAIN_MISMATCH`;
5. `SUCCESSOR_TERMINAL_MISMATCH`;
6. `NON_MONOTONIC_EFFECTIVE_REVISION`;
7. `UNSUPPORTED_REVISION_DISPOSITION`;
8. `COVERAGE_GAP`;
9. `PROJECTED_OVERLAP`.

The canonical failure body contains `type`, `schema_version`, full request, `request_hash`, `code`, `lineage_key`, and `subject_ids`; its constructor recomputes the first applicable failure. Malformed exact types, noncanonical text/hash, invalid rates, and empty targets are constructor errors. Failure returns no partial RuleBook.

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
- `retrospective_availability` carries the old composition instant separately from actual closure/publication availability and `official_record_as_of`;
- `closure_binding` contains the closure key/version/hash and ordered terminal hashes;
- `projection_binding` contains algorithm ID, projection hash, and both execution RuleBook hashes;
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

The function canonical-rebuilds and hash-pins the exact declaration, emits exactly five events atomically in required-dimension order, and uses v2 capability/stream/event/bundle identities. Event `available_time` is the actual retrospective closure/publication availability.

Builder production imports neither Trading Kernel nor Runtime. It consumes already-canonical authority bodies and does not reconstruct economics. The function is not exported from `crypto_quant_bundle_builder.__init__`. No generic publication framework is added.

Publish through unchanged G12C validation and G12D idempotent publication. Repeated publication must return identical manifest, event, stream, retention, and Bundle identities.

## G12H analyzer RED after F3

Only after F3 passes may RED tests freeze the existing pure atomic analyzer contract. The intended module is one concrete Builder module, `rule_coverage.py`, with no provider lookup, economic evaluator, Runtime/Kernel import, registry, or root export.

The analyzer consumes only the explicit v2 declaration and published manifest/events. It does not parse official notices, rerun F2 economics, discover dimensions from `ProfilePortType`, or enumerate Kernel classes.

### Canonical success and failure

`RuleCoverageReport` canonical body fields are:

```text
type, schema_version, declaration_hash, authority_build_hash,
bundle_manifest_hash, target_coverage, official_record_as_of,
closure_hash, projection_hash, required_dimensions, dimension_coverage
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
- declaration/Bundle/profile-context/target mismatch fails atomically;
- closure, projection, RuleBook, authority-body, source, event, or manifest mutation fails;
- closure/publication availability before required evidence, or record cutoff before target end, fails;
- gap at target start/middle/end and overlap at every boundary fail in dimension order;
- exact half-open adjacency passes; target-end equality is not overlap;
- calendar local-date and UTC dimensions preserve their declared domains;
- market-fee applicability keeps handling/regulatory/transfer source tuples distinct;
- repeated analysis yields byte-identical report/failure hashes;
- provider, decision-grade, live, and deployment flags cannot become true;
- no Runtime/Kernel import, Builder root export, generic rule model, or second economic engine appears.

## Validation by phase

### F1

- independently verify official domains, bytes, receipts, index range/termination, candidate inventory, and dispositions;
- reconstruct every canonical source/candidate/component/closure hash twice;
- prove the record cutoff and evidence availability are not backdated;
- run gitleaks against captured artifacts and repository diff.

### F2

- focused pure tests for unchanged terminal, in-target successor split, same-effective correction, after-target successor, unresolved repeal, fork/cycle, availability, target clipping, gap/overlap, canonical hashes, forged constructors, and no partial output;
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

This plan does not claim provider/archive completeness, universal broker commission, minimum commission, bundled fees, rebates, official rounding, block trading, after-hours trading, B shares, funds, bonds, Stock Connect, margin/short, non-CNY scope, account-statement parity, live/current qualification, decision grade, or deployment authorization.

Do not modify existing G08E/G08H types or fixtures; existing G12C/D v1 fixtures/projector; the blocker test; registries; shared Acceptance Matrix; plan README; or root exports. Do not merge or push as part of this plan freeze.
