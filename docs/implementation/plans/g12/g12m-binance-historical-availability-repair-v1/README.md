---
id: G12M-BINANCE-HISTORICAL-AVAILABILITY-REPAIR-V1-EXECUTION
status: DECIDED_H3_ROUTE
owner: backtest historical availability and provider qualification
source_plan: ../g12m-binance-historical-availability-repair-v1.md
status_authority: ../../../acceptance-matrix.md
---

# G12M Binance historical-availability repair execution DAG

## Outcome

Record the accepted Wave 0 inputs, the BHA-02 H3 decision, terminated implementation
nodes, and the sole Ready governance route.

The parent plan remains the normative specification. This directory owns execution
order, node contracts, write sets, and acceptance boundaries only.

## Global invariants

- Accepted funding-history v1/v2 bytes, hashes, IDs, fixtures, APIs, and qualification
  flags remain immutable.
- The accepted H3 decision emits no causal authority and terminates the historical
  implementation branch.
- Builder does not import Runtime/Kernel; Runtime does not import Builder; Kernel does
  not import Runtime.
- No second registry, resolver, catalog, repository, provider framework, availability
  DSL, resampler, fallback chain, or grade system.
- Every writer uses an isolated worktree. Acceptance Matrix, G12 README, shared Runtime
  registration seams, main branch, and final commits are single-writer resources.
- `TUSHARE_TOKEN` and all credentials remain outside artifacts, logs, fixtures,
  exceptions, and commits.

## Execution DAG

```text
BHA-00 governance (accepted) ───────────────┐
BHA-01A settlement research (accepted) ─────┼─→ BHA-02 DECIDED_H3
BHA-01B revision research (accepted) ───────┘          │
                                                       ├─× BHA-03 … BHA-09
                                                       │   TERMINATED_H3
                                                       └─→ BHA-10 READY_H3
```

BHA-10 is the only Ready route. No H2 or prospective authorization remains.

## Nodes

| ID | Ready state | Produces | Contract dependencies | Evidence dependencies | Write conflicts |
| --- | --- | --- | --- | --- | --- |
| [BHA-00](bha-00-governance.md) | ACCEPTED | ADR 0009 and four-time governance | parent plan, ADR 0008 | — | acceptance registry |
| [BHA-01A](bha-01a-settlement-authority-research.md) | ACCEPTED | target-effective settlement/availability evidence | parent plan | first-party Binance sources | none; isolated evidence tree |
| [BHA-01B](bha-01b-revision-authority-research.md) | ACCEPTED | revision/correction limitation evidence | parent plan | first-party Binance sources | none; isolated evidence tree |
| [BHA-02](bha-02-availability-authority.md) | DECIDED_H3 | H3 NO_CAUSAL_AUTHORITY decision | BHA-00 | BHA-01A, BHA-01B | decision artifacts only |
| [BHA-03](bha-03-source-v3.md) | TERMINATED_H3 | none | — | — | none |
| [BHA-04](bha-04-profile-authority.md) | TERMINATED_H3 | none | — | — | none |
| [BHA-05](bha-05-execution-bundle.md) | TERMINATED_H3 | none | — | — | none |
| [BHA-06](bha-06-execution-adapter.md) | TERMINATED_H3 | none | — | — | none |
| [BHA-07](bha-07-runtime-fanin.md) | TERMINATED_H3 | none | — | — | none |
| [BHA-08](bha-08-canonical-run.md) | TERMINATED_H3 | none | — | — | none |
| [BHA-09](bha-09-assessment.md) | TERMINATED_H3 | none | — | — | none |
| [BHA-10](bha-10-governance-fanin.md) | READY_H3 | blocked registry state | BHA-02 H3 | accepted decision receipt | acceptance registry/main branch |

## Parallel waves

### Wave 0 — accepted

BHA-00, BHA-01A, and BHA-01B are frozen at the accepted tips bound by BHA-02.

### Wave 1 — decided H3

BHA-02 selected `H3 — NO_CAUSAL_AUTHORITY` and emitted decision artifacts only.

### Waves 2–4 — terminated

BHA-03 through BHA-09 are `TERMINATED_H3`. No source/Profile, Bundle/adapter,
Runtime, Run, or assessment writer starts.

### Governance fan-in — Ready

BHA-10 is the only Ready route.

## WIP policy

- Only the BHA-10 governance writer may start.
- Read-only reviewers may run in parallel after the BHA-02 commit is frozen.
- Consume only the immutable Wave 0 tips and recorded decision hashes.

## Acceptance and merge policy

BHA-10 consumes the accepted H3 decision and is the sole writer for final Acceptance
Matrix and G12 README status. No terminated implementation commit is integrated.

## Proof budget

| Risk | Nodes | Required proof |
| --- | --- | --- |
| High — provider authority/time causality | 01A, 01B, 02 | exact bytes/hashes, canonical decision, independent review |
| Low — registry presentation | 10 | link/status consistency, protected-byte diff, LSP/diff/secret scan |

No executable code changed, so no repository or architecture suite is required by
BHA-02.

## Immediate ready queue

| Priority | Node | Unblocks | Write set | State |
| --- | --- | --- | --- | --- |
| 1 | BHA-10 | final blocked governance fan-in | Acceptance Matrix/G12 README and receipts | READY_H3 |
