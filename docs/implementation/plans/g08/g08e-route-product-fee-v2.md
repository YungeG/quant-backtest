---
id: G08E-ROUTE-PRODUCT-FEE-V2
readiness: ROADMAP
owner: trading-kernel + backtest-runtime
produces:
  - acyclic route/product fee v2 delivery DAG
consumes:
  - ADR 0005
  - immutable G08E/G08H v1 contracts
fan_out: [G12H-EFFECTIVE-UNTIL-SUPERSEDED-V2]
---

# G08E Route/Product-aware China A-share Execution Fee v2 roadmap

## Status authority

This file is the roadmap and dependency authority only. It freezes no unresolved Runtime semantic leaf contract. The domain decision remains [ADR 0005](../../../adr/0005-cn-a-share-fees-require-access-route-and-product-class.md); glossary terms remain in [CONTEXT](../../../../CONTEXT.md).

## Acyclic delivery DAG

```text
G08E/G08H v1 bytes + ADR 0005
             |
             v
G08E-V2A Kernel contract (READY_FOR_CONTRACT_RED)
             |
             v
G08E-V2B Runtime binding (BLOCKED_ON_V2A_PASSED)
             |
             v
G08E-V2C acceptance (BLOCKED_ON_V2A_AND_V2B_PASSED)
             |
             v
G12H F1 DOMESTIC + ORDINARY_A_SHARE only
```

| Node | Status | Owns | Depends on |
| --- | --- | --- | --- |
| [G08E-V2A Kernel](g08e-route-product-fee-v2-kernel.md) | `READY_FOR_CONTRACT_RED` | Exact pure Kernel types, hashes, policies, IDs, projection, exports, byte locks | G08E v1, ADR 0005 |
| [G08E-V2B Runtime binding](g08e-route-product-fee-v2-runtime-binding.md) | `BLOCKED_ON_G08E_V2A_PASSED` | Explicit profile/order selection and additive profile/build/Semantic Run binding behavior | V2A `PASSED` |
| [G08E-V2C acceptance](g08e-route-product-fee-v2-acceptance.md) | `BLOCKED_ON_G08E_V2A_AND_V2B_PASSED` | Fan-in acceptance receipts, legacy parity, full suite, byte locks | V2A `PASSED`, V2B `PASSED` |

There are no back edges: V2A must not require resolved-profile, profile-build, Runtime registration, `ExecutionCaseSemanticSpec`, or Semantic Run facts. V2B must consume—not redefine—V2A interfaces. V2C owns no new economics. G12H F1 depends on **V2C `PASSED`**, never V2A alone.

## Shared invariants

- V1 public signatures, canonical bytes/hashes, fixtures, root exports, registry, Acceptance Matrix, README, and publication artifacts remain unchanged.
- Route/product has no default or inference; ChinaClear and HKSCC are separate charges; non-notional portfolio/instruction/settlement costs are excluded.
- The finite compatibility projection is XSHE-only, nonextending, and uses nonempty deterministic HKSCC not-applicable refs.
- No merge or push belongs to this roadmap.

## Transition rules

1. V2A may enter RED now and may become `PASSED` only with its own exact Kernel acceptance.
2. V2B starts only after V2A interface/identity tests pass; it may narrow no A fact and may add no economics.
3. V2C starts only after both prior nodes pass and is the sole G12H-unblocking gate.
4. A status change is a separate authorized docs change; no node's plan text itself claims implementation or qualification.

Do not add code, fixtures, registry entries, Acceptance Matrix, README, or publication artifacts in this decomposition change.
