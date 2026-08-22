---
id: G07-DURABLE-REBUILD-PROOF-V2-EXECUTION
status_authority: ../../acceptance-matrix.md
node_status_authority: this file
source_plan: ../g07-durable-rebuild-proof-v2.md
base_commit: 3ad3c42a971988db6712aff507ec630c90c0ea1e
---

# G07 durable rebuild proof v2 execution DAG

## Outcome

Execute the [parent contract](../g07-durable-rebuild-proof-v2.md) with one authority
per fact, one writer and one clean commit per repository node, no v1/v2
reinterpretation, and no code before the bounded contract/hash-DAG decision reaches
accepted H1.

The [Acceptance Matrix](../../acceptance-matrix.md) alone owns the initiative Gate
status. This README owns only the current DRP node execution statuses below.

## DAG

```text
DRP-00 READY: bounded contract/hash-DAG/recovery freeze
  ├─ H2 ─× DRP-01..DRP-05 STOPPED
  └─ H1 + Matrix row READY
      ↓ contract
DRP-01 BLOCKED_CONTRACT: minimal Local Reader reopen provenance
      ↓ contract + evidence
DRP-02 BLOCKED_CONTRACT: durable verification observation + fresh recomputation
      ↓ verified observation contract
DRP-03 BLOCKED_CONTRACT: Backtest implementation candidate
      │  Integrity/manifest v2 + canonical-v3 + ref/repository/facade/analysis v2
      ↓ immutable Backtest candidate commit + typed consumer contract
DRP-04 BLOCKED_CROSS_REPO: Platform consumer-v2 commit + exact Backtest gitlink pin
      ↓ immutable Platform commit + typed submodule-pin/consumer evidence
DRP-05 BLOCKED_FAN_IN: Backtest docs-only governance fan-in + Matrix PASSED
```

The graph is acyclic and has six nodes. DRP-00 is the only immediate Ready node. H2
is terminal. H1 freezes the contract, updates the unique Matrix row to `READY`, and
makes DRP-01 the next executable node.

## Nodes and node-status registry

| ID | Current node status | Repository | Produces | Contract dependencies | Evidence dependencies | Write conflicts |
| --- | --- | --- | --- | --- | --- | --- |
| [DRP-00](drp-00-contract-and-hash-dag.md) | READY | Backtest | accepted H1 exact contract or H2 stop, including operator recovery | parent, ADR 0008, accepted G12M prerequisite | base-HEAD source inventory and feasibility | research contract, node registry, new Matrix row |
| [DRP-01](drp-01-attested-local-bundle-open.md) | BLOCKED_CONTRACT | Backtest | exact private repository reopen/read result from the existing Local Reader | DRP-00 H1 | current G12D local publication/retention fixtures | Local Reader private seam |
| [DRP-02](drp-02-proof-and-recomputation.md) | BLOCKED_CONTRACT | Backtest | durable `deterministic_rebuild_verification@1` and proof-publication manifest@1 | DRP-00 H1, DRP-01 | schema-3/PREP/two-Attempt full-trace fixtures | execution/rebuild and proof-publication seam |
| [DRP-03](drp-03-backtest-implementation-candidate.md) | BLOCKED_CONTRACT | Backtest | one implementation candidate commit: Integrity v2, canonical-v3, V2 completed ref/replay/cache, and additive analysis v2 | DRP-02 | legacy goldens plus exact local schema-3 Run | Integrity/publication/ref/repository/facade/analysis seams |
| [DRP-04](drp-04-platform-consumer-v2.md) | BLOCKED_CROSS_REPO | Platform superproject | one consumer-v2 commit pinning the exact DRP-03 Backtest commit | DRP-03 immutable commit | Platform V1 bytes plus consumer-v2 journey | Platform gitlink and consumer contract files |
| [DRP-05](drp-05-governance-fan-in.md) | BLOCKED_FAN_IN | Backtest | docs-only governance commit binding immutable DRP-03 and DRP-04 commits and setting only the unique Matrix row to `PASSED` | DRP-03, DRP-04 | complete Backtest and Platform acceptance evidence | unique Matrix row only |

Only this table owns current DRP node statuses. Node frontmatter records ownership and
dependencies, not a second status.

## Typed edges

| From | To | Type | Consumed artifact |
| --- | --- | --- | --- |
| parent + base evidence | DRP-00 | contract + evidence | invariant set, current source facts, compatibility and recovery constraints |
| DRP-00 H1 + Matrix READY | DRP-01 | contract | exact private Local Reader provenance/reopen mechanism and typed G12D body contract |
| DRP-00 H1 | DRP-02 | contract | exact minimal verification fields, schema catalog, proof-publication manifest, hash DAG, failure/recovery catalog |
| DRP-01 | DRP-02 | contract + evidence | exact repository-open Reader provenance and fresh reopen/tamper evidence |
| DRP-02 | DRP-03 | contract + evidence | exact read-back verified observation, mismatch evidence, dedicated publication bytes, and recovery simulations |
| DRP-03 Backtest candidate commit | DRP-04 Platform commit | cross-repo implementation + submodule-pin | immutable Backtest SHA; V1/V2 completed/analysis dispatch contract; public roots only |
| DRP-03 Backtest candidate commit | DRP-05 | immutable implementation evidence | exact Backtest candidate SHA and Backtest validation record |
| DRP-04 Platform commit | DRP-05 | cross-repo consumer + submodule-pin evidence | immutable Platform SHA whose `backtest` gitlink equals the DRP-03 SHA and whose consumer-v2 journey passes |
| DRP-00 H2 | DRP-01..DRP-05 | stop | immutable blocker decision; no placeholder output |

## Exact future write-set ownership

| Node | Repository | Exact future write set |
| --- | --- | --- |
| DRP-00 | Backtest | `docs/research/g07-durable-rebuild-proof-v2-contract.md`; `docs/implementation/acceptance-matrix.md` (only the new row, H1 `READY` or H2 blocker); `docs/implementation/plans/g07-durable-rebuild-proof-v2/README.md`; `docs/implementation/plans/g07-durable-rebuild-proof-v2/drp-00-contract-and-hash-dag.md` |
| DRP-01 | Backtest | `packages/market-data-contracts/src/crypto_quant_market_data/local_market_bundle_reader.py`; focused Local Reader provenance/reopen test selected by DRP-00; no package-root export file |
| DRP-02 | Backtest | minimum backtest-runtime private rebuild/publication module(s) selected by DRP-00; `packages/backtest-runtime/src/crypto_quant_backtest/execution_inputs.py` only if an existing private exact decoder cannot be reused unchanged; focused verification/recomputation/durable-publication and cooperative recovery simulation tests; one additive verification golden |
| DRP-03 | Backtest | `packages/backtest-runtime/src/crypto_quant_backtest/integrity.py`; `packages/backtest-runtime/src/crypto_quant_backtest/publication_refs.py`; `packages/backtest-runtime/src/crypto_quant_backtest/verified_publications.py`; `packages/backtest-runtime/src/crypto_quant_backtest/analysis.py`; `packages/backtest-runtime/src/crypto_quant_backtest/analysis_derivation.py`; `packages/backtest-runtime/src/crypto_quant_backtest/evidence_repository.py`; `packages/backtest-runtime/src/crypto_quant_backtest/facade.py`; `packages/backtest-runtime/src/crypto_quant_backtest/__init__.py`; `packages/backtest-runtime/src/crypto_quant_backtest/runner.py` only if exact canonical-v3 cache recognition requires it; minimum private publication support selected by DRP-00; focused Integrity/publication/ref/repository/facade/analysis tests, architecture tests, and additive exact goldens selected by DRP-00 |
| DRP-04 | Platform superproject (`../`) | `../tests/contracts/backtest-consumer-port-v2.json`; `../tests/support/backtest_consumer_port.py`; `../tests/architecture/test_backtest_consumer_port.py`; `../backtest` gitlink only. `../tests/contracts/backtest-consumer-port-v1.json` is protected and unchanged |
| DRP-05 | Backtest | `docs/implementation/acceptance-matrix.md` only, and only the unique `G07-DURABLE-REBUILD-PROOF-V2` row |

DRP-00 freezes exact conditional private/test paths before implementation. A node may
omit a listed conditional file when caller tracing proves no edit is needed; it may
not add a public Runtime method, Local Reader root export, finalized result/outcome
wrapper, second repository, repository root/path argument, resolver, registry,
Reader/provider/recovery framework, Builder import, Resolution policy edit, or v1/v2
fixture rewrite. The additive public surface is limited to the V2 completed and
analysis contracts required by canonical-v3.

## Commit and WIP policy

- One active writer in one repository at a time.
- Each node ends with a clean repository and exactly one node commit before its typed
  successor starts; no node commit mixes Backtest and Platform writes.
- DRP-03 records the immutable Backtest implementation-candidate SHA. DRP-04 starts
  only from that SHA and its Platform commit sets `../backtest` to exactly it.
- DRP-05 is a later Backtest docs/status-only commit. Platform may and should remain
  pinned to the exact DRP-03 code commit because DRP-05 changes no code, public bytes,
  consumer contract, or submodule behavior.
- Before H1: one research/contract writer; zero code writers. After H1 and Matrix
  `READY`: nodes execute in numeric order.
- Read-only review may run in parallel. Shared status, integration, commit, amend, and
  push remain serialized.
- No skeleton proof module, placeholder schema, new root export, or test-only
  provenance constructor while DRP-00 is open.

## Failure precedence

1. DRP-00 H2: an exact additive field/hash/layout/provenance/analysis/recovery contract
   cannot be frozen.
2. DRP-01: the exact existing Local Reader cannot retain and freshly replay repository
   provenance without changing its public constructor/open/root API.
3. DRP-02 pre-Integrity: after lane selection, fresh reopen/tamper, acquisition,
   exact decode, recomputation, structural construction, lock acquisition, durable
   publication, or final read-back fails; no legacy fallback is permitted.
4. DRP-03: a valid durable observation cannot bind Integrity, canonical-v3 static
   replay/cache, or the additive completed-v3→analysis-v2 path while preserving V1.
5. DRP-04: Platform cannot pin the exact candidate and dispatch the V1/V2 consumer
   journey without heuristic unwrap, downgrade, or v1 fixture changes.
6. DRP-05: either immutable commit/evidence edge is missing or the Matrix row cannot
   be updated without changing another authority.

Semantic comparison inequality is not item 3. DRP-02 durably records it, then DRP-03
publishes FAILED. Development/ineligible Profile/Build or incompatible Environment is
an existing pre-Attempt Resolution failure, not a v2 BLOCKED result. A BLOCKED v2 case
is retained only if DRP-00 proves a compatible decision-grade environment with an
explicit limitation is reachable under current policy.

## Proof budget

| Risk | Nodes | Required proof |
| --- | --- | --- |
| High — provenance | 00, 01, 02 | exact Local Reader/open provenance, direct/in-memory/arbitrary/subclass non-attestation, fresh reopen, no path serialization |
| High — local retention claim | 01, 02, 03 | exact current G12D publication/retention bodies/hashes and retrievability; explicit future/trusted-root/remote/copied-tree nonclaims |
| High — deterministic rebuild | 02, 03 | fresh schema-3 decode, Bundle/PREP/Resolution/case/rebuild, durable comparison observation, mismatch→FAILED, same-build ceiling |
| High — durability/recovery | 00, 02, 03 | staging→verify→harden→rename→fsync; operator exclusivity; exact scoped cleanup; staging non-adoption; later under-lock exact-final verification; unsafe cleanup refusal |
| High — grade firewall | 03, 05 | Resolution precedes proof; Integrity alone grades; no provider qualification; deployment false |
| High — replay/cache | 03 | repository static graph replay cannot claim local durability; cache separately verifies the exact local proof directory and mirrored graph; canonical-v2 no fallback |
| High — cross-repo fan-in | 03, 04, 05 | immutable Backtest candidate SHA, exact Platform gitlink pin, immutable Platform SHA, typed evidence edges, one clean commit per repo/node |
| Medium — additive analysis | 00, 03, 04 | `BacktestAnalysisV2`, `AnalysisArtifactRefV2`, verified completed-v3 input, same `derive` operation dispatch, `load_analysis_v2`, V1 exact preservation |
| Low — docs/status | 00, 05 | Matrix/DAG authority, frontmatter/links, source hashes, docs-only fan-in diff, gitleaks |

## Stop rules

DRP-00 records exactly one route:

- **H1 `CONTRACT_FROZEN`:** exact private Reader seam, minimal fields, wire/analysis
  catalog, both manifests, hash preimages, failure codes, cooperative recovery
  authority/order, layouts, Resolution boundary, and public/API preservation are
  frozen; update only the new Matrix row to `READY` and mark DRP-01 Ready.
- **H2 `CONTRACT_BLOCKED`:** record the first immutable conflict, keep the new Matrix
  row non-READY with the blocker, mark DRP-01..05 STOPPED, and emit no code.

A TBD field, optional authority rule, generic mapping, choose-later layout, public
facade addition, generic artifact-store durability claim, heuristic version unwrap,
equality-before-observation rule, or automatic unsafe recovery is H2 rather than
implementation discretion.

## Immediate Ready queue

| Priority | Node | Node state | Unblocks | Write ownership |
| --- | --- | --- | --- | --- |
| 1 | DRP-00 | READY | DRP-01 on H1 + Matrix READY, or terminal H2 | bounded research contract, node registry, new Matrix row only |
| 2 | DRP-01 | BLOCKED_CONTRACT | DRP-02 | Local Reader private seam only |
| 3 | DRP-02 | BLOCKED_CONTRACT | DRP-03 | verification/recomputation/durable proof publication only |
| 4 | DRP-03 | BLOCKED_CONTRACT | DRP-04 | one Backtest implementation candidate commit |
| 5 | DRP-04 | BLOCKED_CROSS_REPO | DRP-05 | one Platform consumer-v2/gitlink commit |
| 6 | DRP-05 | BLOCKED_FAN_IN | accepted generic prerequisite | one Backtest Matrix-row-only governance commit |

## Final acceptance route

DRP-05 may update the unique Matrix row to `PASSED` only when:

- DRP-00 H1 is immutable and every predecessor is accepted;
- the immutable DRP-03 Backtest candidate implements the exact schema-3
  requested-decision-grade journey through canonical-v3, returns
  `BacktestCanonicalPublicationRefV2`, verifies current local proof state, replays the
  static graph through `load_completed_v3`, and preserves canonical-v2/V1 behavior;
- the same candidate additively supports completed-v3 analysis through the unchanged
  `BacktestAnalysisRuntime.derive` operation, `BacktestAnalysisV2`,
  `AnalysisArtifactRefV2`, a verified completed-v3 input, and
  `load_analysis_v2`, with no heuristic unwrap or downgrade;
- mismatch produces a durable observation plus FAILED evaluation; BLOCKED is included
  only when source-proven reachable after Resolution;
- cooperative recovery simulations prove cleanup/retry for safe exact scoped residue
  and refusal for malformed/partial/conflicting final state;
- the immutable DRP-04 Platform commit pins `../backtest` to exactly the DRP-03 SHA,
  leaves the v1 fixture byte-exact, and passes
  `run → load_completed_v3 → derive → load_analysis_v2` plus V1 dispatch/operations;
- full Backtest and Platform suites, architecture, Markdown/frontmatter/links/source/
  DAG checks, repo-specific diff checks, and gitleaks pass; and
- DRP-05 changes only the unique Matrix row, binding both immutable SHAs and exact
  commands/results/artifact hashes.

Accepted historical `G07 PASSED` and all G12M/provider facts remain unchanged.
