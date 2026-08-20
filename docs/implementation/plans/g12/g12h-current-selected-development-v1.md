---
id: G12H-CURRENT-SELECTED-DEVELOPMENT-V1
proposed_readiness: READY_FOR_D1_SNAPSHOT
registry_status: SEE_PARENT_ACCEPTANCE_MATRIX
owner: trading-kernel values + market-bundle-builder publication
produces:
  - current-selected development authority snapshot v1
  - finite July-2026 route/product fee RuleBooks v2
  - additive five-dimension development declaration/publication v2
depends_on:
  contract: [G08E-ROUTE-PRODUCT-FEE-V2C, G12C, G12D]
  evidence: [G12H-LIVE-STATUS-API-PROBES-V1, ADR-0007]
  write_conflict: [builder-rule-publication, acceptance-registry]
---

# G12H current-selected development v1

## Boundary

This is the additive option-B path accepted by [ADR 0007](../../../adr/0007-current-official-selection-supports-development-projection.md). It does not replace or pass the strict [effective-until-superseded plan](g12h-effective-until-superseded-v2.md). Strict `official_record_as_of` successor closure remains blocked.

The exact scope is XSHE, `EQUITY`, CNY quote/settlement, `AUCTION`, all boards admitted by the bound profile, `DOMESTIC`, `ORDINARY_A_SHARE`, and `trade_notional`, for:

```text
[2026-07-05T16:00:00Z, 2026-07-30T16:00:00Z)
```

No v1 artifact, V2A compatibility artifact, root export, Runtime branch, or public API changes.

## D1 — current-selected development snapshot

Freeze one canonical JSON body:

```text
{
  type: "cn_a_share_current_selected_development_authority_snapshot",
  schema_version: 1,
  snapshot_key,
  snapshot_version,
  semantics_id: "current-official-selection-development.v1",
  target_scope,
  target_from,
  target_to_exclusive,
  development_evidence_available_at,
  components,
  economics,
  qualification,
  limitations
}
```

`components` contains exactly the five lineages in order: `exchange_handling`, `securities_regulatory`, `chinaclear_transfer`, `hkscc_transfer`, `stamp_duty`. Each binds exact source path and URL, raw hash, response-header hash, redirect-chain hash, receipt hash, `observed_at` equal to the verified receipt time, and canonically ordered candidate dispositions. Every known candidate is classified as selected, no economic effect, before target/already represented, after target, prospective/not implemented, or unresolved. An unresolved candidate, contradictory selected content, scope/effective-time conflict, or source/hash mismatch fails D1 atomically. `development_evidence_available_at` is the latest bound receipt. The body has no `official_record_as_of`.

`economics` freezes one target state per lineage:

```text
exchange_handling:    applies=true,  rate=Rate(341, 7), buy=true,  sell=true
securities_regulatory: applies=true, rate=Rate(2, 5),   buy=true,  sell=true
chinaclear_transfer:  applies=true,  rate=Rate(1, 5),   buy=true,  sell=true
hkscc_transfer:       applies=false, rate=Rate(0, 0),   buy=false, sell=false
stamp_duty:           applies=true,  rate=Rate(5, 4),   buy=false, sell=true
```

Every basis is `trade_notional`. Snapshot reconstruction recomputes all hashes and rejects missing components, scope drift, target drift, source/hash mismatch, empty applicable refs, a nonempty HKSCC rate, or any qualification overclaim.

Only `development_projection_authorized=true`; official successor closure, provider authority/completeness, rule-coverage qualification, decision grade, live, and deployment remain false.

## D2 — finite existing v2 RuleBooks

No new Kernel projector or type is required. Construct existing `CnAShareMarketFeeBandV2`, `CnAShareStampDutyBandV2`, `CnAShareMarketFeeRuleBookV2`, and `CnAShareStampDutyRuleBookV2` values with exactly one target band each.

New identities:

```text
equity.cn_a_share.cash.market-fees.domestic.ordinary-a-share.current-selected-development.v2
equity.cn_a_share.cash.stamp-duty.domestic.ordinary-a-share.current-selected-development.v2
```

Use `rule_book_version=2`. Source refs are nonempty, canonical, and derived from stable finite target-economic semantics, not snapshot/capture/publication hashes. Therefore unchanged economics may retain identical RuleBook bytes under later evidence; changed economics must change the affected RuleBook hash.

The snapshot and RuleBooks are frozen in a new declaration fixture. Tests reconstruct every nested exact type, assert canonical bytes/hashes, target coverage, separate ChinaClear/HKSCC components, seller-only stamp duty, and constructor-bypass rejection. Existing v1/V2A fixture hashes must remain unchanged.

## D3 — additive Builder publication

Add one off-root module only:

```text
packages/market-bundle-builder/src/crypto_quant_bundle_builder/cn_a_share_current_selected_rule_bundle.py
```

It exposes one module-local operation:

```python
project_cn_a_share_current_selected_rule_authority_events_v2(
    declaration: Mapping[str, object],
    /,
) -> tuple[MarketEvent, ...]
```

The function canonical-rebuilds and hash-pins the exact declaration, then emits exactly five events in required-dimension order. Calendar, order-rules, and corporate-action bodies are reused byte-for-byte from v1. Market-fee and stamp-duty bodies are the D2 v2 RuleBooks. Event `available_time` is `development_evidence_available_at`. Use new v2 capability, event, stream, source, bundle, retention, and publication identities.

Builder imports neither Kernel nor Runtime, does not reconstruct economics, and does not export the function from package root. Publish through unchanged G12C validation and G12D repository; repeated publication is byte-identical and idempotent.

## D4 — G12H development coverage

Only after D3 passes, freeze the smallest deterministic G12H report/failure interface against the v2 declaration. It may report complete finite target intervals for the five declared dimensions while separately retaining:

```text
official_successor_closure_complete = false
provider_authority_qualified = false
provider_completeness_qualified = false
rule_coverage_qualified = false
decision_grade_eligible = false
live_eligible = false
deployment_authorized = false
```

Coverage completeness must never be presented as legal/history completeness.

## Validation

- D1/D2: exact source/hash reconstruction, canonical nested types, mutation matrix, one-band target economics, v1/V2A hash preservation.
- D3: five exact events, G12C validation, G12D first/repeated publication, no Kernel/Runtime/root imports.
- D4: exact target coverage, gap/overlap failures, deterministic precedence, explicit qualification separation, and mandatory `rule_coverage_qualified=false` despite a complete finite development interval report.
- Every phase: focused pytest, architecture checks, `uv lock --check`, `git diff --check`, gitleaks, and independent review.

## Nonclaims

No historical successor completeness, official `official_record_as_of`, Northbound, preferred-stock, ETF, universal broker commission, minimum commission, rounding, non-notional costs, decision-grade, live, or deployment claim.
