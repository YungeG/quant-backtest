---
id: G08E-ROUTE-PRODUCT-FEE-V2B
proposed_readiness: SEE_PARENT_ACCEPTANCE_MATRIX
registry_status: SEE_PARENT_ACCEPTANCE_MATRIX
owner: backtest-runtime profile/build binding
produces:
  - explicit route/product selection from immutable profile/order context
  - additive v2 profile/build and Semantic Run financial binding
consumes:
  - G08E-V2A frozen Kernel interfaces
  - immutable G08H v1 resolved-profile contract
depends_on:
  contract: [G08E-ROUTE-PRODUCT-FEE-V2A]
  evidence: [G08E-V2A-PASSED]
  write_conflict: [runtime-cn-a-share-profile-binding, runtime-semantic-identity]
fan_out: [G08E-ROUTE-PRODUCT-FEE-V2C]
---

# G08E-V2B Runtime route/product binding

## Status

The parent [Acceptance Matrix](../../acceptance-matrix.md) is the sole current status authority; this frontmatter delegates status to that registry. This plan records the accepted private Runtime behavior, ownership, and exclusions. The immutable implementation source and validation evidence are recorded by [V2C](g08e-route-product-fee-v2-acceptance.md#acceptance-closure).

## Required outcomes

After V2A passes, Runtime must:

1. select explicit access route and fee product from immutable profile/order context, never symbol, stable key, account permission, current metadata, or defaults;
2. reject any profile/order context outside the selected A Scope before fee binding;
3. use only the exact A Authority and paired A market/stamp books selected for this execution;
4. create a new additive profile/build identity that hash-binds the immutable v1 profile/build inputs, selected A Authority hash, A Scope/selection/book/component identities, and the financial semantic identity used before execution;
5. bind identity in one strict direction only: `V2A Authority -> additive profile identity -> additive build identity -> financial_inputs_hash -> Semantic Run`; Runtime must not feed a Semantic Run, financial input, build identity, or profile identity back into V2A Authority, books, Scope, selection, or economics;
6. require the Kernel policy to receive the execution-selected expected A Authority; a substitution must fail before fee query use;
7. retain the frozen v1 `CnAShareResolvedProfile`, root exports, registry entries, journey bytes, and Semantic Run behavior unchanged for v1 callers.

This is canonical builder-equivalence and runtime semantic binding, not a claim of cryptographic provenance or external-source qualification.

## Owned seam and write set

V2B owns one private, profile-specific Runtime binding seam beside the existing A-share profile module, one additive v2 profile/build registration/binding, and focused Runtime/support/architecture tests. It may add the minimal v2-only composition/semantic-input integration needed to carry the selected A identity before execution. The exact module split, names, field lists, canonical types, and registration leaf identities are deferred until A `PASSED`. The later profile and build preimages must explicitly exclude request identity, dispatcher/spec identity, `financial_inputs_hash`, and Semantic Run identity; only the downstream financial-input preimage may bind build identity, and only the downstream Semantic Run preimage may bind `financial_inputs_hash`.

It may not modify G08H v1 declarations/composer identity, generic Engine/Runner behavior, generic registry semantics, Builder, provider adapters, global roots, Acceptance Matrix, README, fixtures, or v1 manifest/profile/Semantic Run bytes. No generic route/product framework, second fee engine, provider lookup, current metadata lookup, or fallback is allowed.

## Entry and exit gates

- **Entry:** parent Acceptance Matrix V2A `PASSED` registry fact, including exact A exports, canonical identities, failure precedence, protected bytes, and independent review closure.
- **RED:** freeze only Runtime behavior derived from A's accepted interfaces; do not revise A economics or canonical leaves.
- **GREEN:** prove explicit immutable selection, no direct Authority substitution, additive v2 profile/build identity change on Authority mutation, and exact v1 byte preservation.
- **Exit:** focused Runtime tests, semantic-identity tests, v1 regression/full suite, immutable receipts, import checks, mypy, lock, gitleaks, diff/status, and independent review. Only then may V2B become `PASSED`.

## Nonclaims

V2B does not add Northbound/preferred/ETF economics, July-2026 evidence, provider completeness, decision grade, live/deployment authorization, or non-notional costs. G12H remains blocked until V2C, not V2B alone, passes.
