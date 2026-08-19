---
id: G08E-ROUTE-PRODUCT-FEE-V2B
readiness: BLOCKED_ON_G08E_V2A_PASSED
gate_status: DRAFT
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

`BLOCKED_ON_G08E_V2A_PASSED`. This plan freezes behavioral outcomes, ownership, and exclusions only. It must not freeze Runtime field lists, canonical preimages, import sets, helper signatures, manifest leaf hashes, or registration leaves until V2A's pure Kernel interfaces are accepted. Those are deliberately unresolved here.

## Required outcomes

After V2A passes, Runtime must:

1. select explicit access route and fee product from immutable profile/order context, never symbol, stable key, account permission, current metadata, or defaults;
2. reject any profile/order context outside the selected A Scope before fee binding;
3. use only the exact A Authority and paired A market/stamp books selected for this execution;
4. create a new additive profile/build identity that hash-binds the immutable v1 profile/build inputs, selected A Authority hash, A Scope/selection/book/component identities, and the financial semantic identity used before execution;
5. inject that additive identity into the v2 request/Semantic Run financial input so a structurally valid substituted Authority cannot retain the same execution identity;
6. require the Kernel policy to receive the execution-selected expected A Authority; a substitution must fail before fee query use;
7. retain the frozen v1 `CnAShareResolvedProfile`, root exports, registry entries, journey bytes, and Semantic Run behavior unchanged for v1 callers.

This is canonical builder-equivalence and runtime semantic binding, not a claim of cryptographic provenance or external-source qualification.

## Owned seam and write set

V2B owns one private, profile-specific Runtime binding seam beside the existing A-share profile module, one additive v2 profile/build registration/binding, and focused Runtime/support/architecture tests. It may add the minimal v2-only composition/semantic-input integration needed to carry the selected A identity before execution. The exact module split, names, field lists, canonical types, preimages, and registration leaf identities are deferred until A `PASSED`.

It may not modify G08H v1 declarations/composer identity, generic Engine/Runner behavior, generic registry semantics, Builder, provider adapters, global roots, Acceptance Matrix, README, fixtures, or v1 manifest/profile/Semantic Run bytes. No generic route/product framework, second fee engine, provider lookup, current metadata lookup, or fallback is allowed.

## Entry and exit gates

- **Entry:** V2A `PASSED`, including exact A exports, canonical identities, failure precedence, protected bytes, and independent review receipt.
- **RED:** freeze only Runtime behavior derived from A's accepted interfaces; do not revise A economics or canonical leaves.
- **GREEN:** prove explicit immutable selection, no direct Authority substitution, additive v2 profile/build identity change on Authority mutation, and exact v1 byte preservation.
- **Exit:** focused Runtime tests, semantic-identity tests, v1 regression/full suite, immutable receipts, import checks, mypy, lock, gitleaks, diff/status, and independent review. Only then may V2B become `PASSED`.

## Nonclaims

V2B does not add Northbound/preferred/ETF economics, July-2026 evidence, provider completeness, decision grade, live/deployment authorization, or non-notional costs. G12H remains blocked until V2C, not V2B alone, passes.
