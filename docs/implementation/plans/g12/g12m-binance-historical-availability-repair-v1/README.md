---
id: G12M-BINANCE-HISTORICAL-AVAILABILITY-REPAIR-V1-EXECUTION
status: DRAFT_EXECUTION_DAG
owner: backtest historical availability and provider qualification
source_plan: ../g12m-binance-historical-availability-repair-v1.md
status_authority: ../../../acceptance-matrix.md
---

# G12M Binance historical-availability repair execution DAG

## Outcome

Split the accepted repair specification into vertical, independently reviewed nodes
that can run in isolated worktrees and converge through one Runtime integration writer
and one governance writer.

The parent plan remains the normative specification. This directory owns execution
order, node contracts, write sets, and acceptance boundaries only.

## Global invariants

- Accepted funding-history v1/v2 bytes, hashes, IDs, fixtures, APIs, and qualification
  flags remain immutable.
- H1 requires `provider_available_time == funding_time == settlement instant`; H2/H3
  terminate the historical implementation branch.
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
BHA-00 governance ───────────────┐
BHA-01A settlement research ─────┼─→ BHA-02 authority gate/value
BHA-01B revision research ───────┘          │
                                            ├─→ BHA-03 source v3 ──┬─→ BHA-05 execution Bundle ─┐
                                            └─→ BHA-04 Profile ────┼─→ BHA-06 execution adapter ┼─→ BHA-07 Runtime fan-in
                                                                   │                            │
                                                                   └────────────────────────────┘
                                                                                  ↓
                                                                         BHA-08 canonical Run
                                                                                  ↓
                                                                         BHA-09 G12M assessment
                                                                                  ↓
                                                                         BHA-10 governance fan-in
```

BHA-02 routes H2 to a separate prospective plan and H3 directly to BHA-10 as a
permanent blocker. Neither route starts BHA-03 through BHA-09.

## Nodes

| ID | Ready state | Produces | Contract dependencies | Evidence dependencies | Write conflicts |
| --- | --- | --- | --- | --- | --- |
| [BHA-00](bha-00-governance.md) | READY | ADR 0009 and four-time governance | parent plan, ADR 0008 | — | acceptance registry |
| [BHA-01A](bha-01a-settlement-authority-research.md) | READY | target-effective settlement/availability evidence | parent plan | first-party Binance sources | none; isolated evidence tree |
| [BHA-01B](bha-01b-revision-authority-research.md) | READY | revision/correction limitation evidence | parent plan | first-party Binance sources | none; isolated evidence tree |
| [BHA-02](bha-02-availability-authority.md) | WAITING | H1/H2/H3 decision; H1 canonical availability authority | BHA-00 | BHA-01A, BHA-01B | Builder authority module |
| [BHA-03](bha-03-source-v3.md) | WAITING_H1 | additive funding-history v3 report/Event stream | BHA-02 H1 | accepted v2 report | Builder v3 module/fixtures |
| [BHA-04](bha-04-profile-authority.md) | WAITING_H1 | Profile authority inputs and exact capability contract | BHA-02 H1 | existing component authorities | additive Profile-authority input module |
| [BHA-05](bha-05-execution-bundle.md) | WAITING | one complete execution Bundle | BHA-03, BHA-04 | exact component streams | Bundle fixtures/publication |
| [BHA-06](bha-06-execution-adapter.md) | WAITING | Event-to-G10E adapter and lineage crosswalk | BHA-03, BHA-04 | existing G10E types | Runtime adapter module |
| [BHA-07](bha-07-runtime-fanin.md) | WAITING_WRITE_CONFLICT | accepted Profile registration and Runtime consumption | BHA-04, BHA-05, BHA-06 | — | shared Runtime seams; current dirty profile file |
| [BHA-08](bha-08-canonical-run.md) | WAITING | persisted decision-grade Run and accounting proof | BHA-05, BHA-07 | exact v3/Bundle/Profile identities | Runtime journey fixtures |
| [BHA-09](bha-09-assessment.md) | WAITING | read-only provider-specific G12M assessment | BHA-02, BHA-03, BHA-05, BHA-06, BHA-08 | canonical Run bytes | Runtime assessor module |
| [BHA-10](bha-10-governance-fanin.md) | WAITING | accepted or blocked registry state | BHA-09 or BHA-02 H2/H3 | all acceptance receipts | acceptance registry/main branch |

## Parallel waves

### Wave 0 — start now

Run BHA-00, BHA-01A, and BHA-01B concurrently in three isolated worktrees. BHA-00
owns governance files; the research nodes own disjoint research/evidence paths.

### Wave 1 — authority gate

One writer executes BHA-02 after all Wave 0 outputs are frozen and independently
reviewed. This node is the only H1/H2/H3 decision owner.

### Wave 2 — source/Profile fan-out

After H1, run BHA-03 and BHA-04 concurrently. They consume BHA-02's frozen
authority identity and exact v3 funding capability/payload contract. BHA-03 publishes
the source; BHA-04 closes non-registration Profile authority inputs. They must not
modify each other's package or fixtures.

### Wave 3 — Bundle/adapter fan-out

After BHA-03 and BHA-04, run BHA-05 and BHA-06 concurrently. BHA-05 owns Bundle
composition; BHA-06 owns Runtime-to-Kernel conversion. Neither claims the final
resolved Profile identity, registers the Profile, or edits shared Runtime
orchestration; BHA-07 owns that fan-in.

### Wave 4 — serialized fan-in

BHA-07, BHA-08, BHA-09, and BHA-10 are serialized. They touch shared registration,
canonical execution, assessment identity, or registry state.

## WIP policy

- Wave 0: at most one governance writer plus two research writers.
- Waves 2 and 3: at most two implementation writers, each in its own worktree.
- BHA-07 onward: exactly one writer.
- Read-only reviewers may run in parallel with any writer after that writer freezes a
  candidate commit.
- Do not start a dependent node from an uncommitted sibling worktree; consume an
  immutable commit and recorded artifact hashes.

## Acceptance and merge policy

Each node produces one implementation/research commit and one independent review.
Record executed commands and hashes under `receipts/` only after acceptance; receipts
must not restate the plan.

Integration order is topological. Cherry-pick only accepted commits. BHA-07 must not
start until the current uncommitted changes in
`packages/backtest-runtime/src/crypto_quant_backtest/binance_usdm_profile.py` have
been reconciled by their owner. BHA-10 is the sole writer for final Acceptance Matrix
and G12 README status.

## Proof budget

| Risk | Nodes | Required proof |
| --- | --- | --- |
| High — provider authority/time causality | 01A, 01B, 02, 03, 06 | exact bytes/hashes, canonical reconstruction, adversarial timing/revision tests, independent review |
| High — grade/accounting/identity | 04, 07, 08, 09 | fail-closed grade resolution, persisted replay, Integrity verification, trace/accounting identity, golden assessment |
| Medium — Bundle composition/shared seams | 05, 07 | capability resolution, exact manifest membership, architecture boundaries, adjacent suite |
| Low — registry presentation | 00, 10 | link/status consistency, protected-byte diff, LSP/diff/secret scan |

Run the full repository and full architecture suites once at BHA-08 and again only if
BHA-09/BHA-10 changes executable code or shared policy. Focused node tests are
required at every implementation commit.

## Immediate ready queue

| Priority | Node | Unblocks | Write set | State |
| --- | --- | --- | --- | --- |
| 1 | BHA-01A | historical H1/H2 decision | settlement research/evidence only | READY |
| 2 | BHA-01B | revision limitation closure | revision research/evidence only | READY |
| 3 | BHA-00 | all implementation acceptance | ADR/context/governance only | READY |
| 4 | BHA-02 | every code node | queued single-writer authority module | BLOCKED_BY_WAVE_0 |
