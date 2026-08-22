---
id: DRP-00
owner: backtest-runtime-contract
status_authority: README.md
produces:
  - accepted exact type/version/field/provenance/publication/analysis/recovery catalog and hash DAG, or H2 stop
consumes:
  - ../g07-durable-rebuild-proof-v2.md
  - ADR 0008
  - base-HEAD Backtest and Platform source inventory
depends_on:
  contract: []
  evidence: [base-head-source-hashes, platform-v1-consumer-source-hashes]
  write_conflict: [drp-status-research-contract-new-matrix-row]
---

# DRP-00 contract and hash-DAG freeze

## Caller-visible result

Publish one bounded research contract that makes the parent executable without leaving
artifact authority, minimal field shape, private Reader provenance, analysis-version
compatibility, failure precedence, cooperative recovery, cross-repository ordering, or
atomic layout to the implementer. This node writes no package, test, fixture, old
`G07` status, Platform file, or G12M receipt.

## Required H1 contract

Freeze all of the following exactly:

1. `BacktestRuntime.run(request)` exact unchanged parameters and lane predicate:
   exact schema 3 + requested decision grade + exact `LocalMarketBundleReader` type +
   presence of private `open` provenance, selected before any fresh reopen; no new
   Runtime method and no fallback after selection;
2. the smallest private provenance retained only by
   `LocalMarketBundleReader.open`, the one exact versioned package-internal
   read/reopen interface, its private exact result, and why direct construction,
   subclassing, in-memory, and arbitrary Readers never attest while constructor/open/
   root exports remain exact; direct construction remains the current non-attested/
   blocked path, while stale/tampered selected provenance fails pre-Integrity;
3. exact current G12D publication/retention body decoding, hashes, and retrievability
   claim, including future-policy/trusted-root/remote/copied-tree nonclaims;
4. exact proof/result/ref catalog: new verification@1 and proof-publication-manifest@1;
   canonical-attempt-ref@2; Integrity context/report@2; completed Result@3; canonical
   publication manifest@2; evaluation record@2 only because v1 exact-binds
   `IntegrityReport`; additive nominal `BacktestCanonicalPublicationRefV2` exact over
   manifest@2; preserved V1 constructor, wire, and behavior; `RunPublicationRef`/
   facade union adds only V2 and leaves raw `ArtifactRef` for terminal/evaluation,
   never canonical-v3 COMPLETED;
5. exact additive analysis catalog for canonical-v3: `BacktestAnalysisV2` stored as
   `backtest_analysis@2`; `AnalysisArtifactRefV2` exact over that schema;
   `VerifiedBacktestAnalysisV2`; minimum `VerifiedCompletedPublicationV3` returned by
   `load_completed_v3`; and `load_analysis_v2(AnalysisArtifactRefV2)`. Freeze exact
   fields, canonical wire tags, root exports, failure dispositions, and protected
   fingerprints. Preserve every current `BacktestAnalysis`, `AnalysisArtifactRef`,
   `VerifiedBacktestAnalysis`, verified completed V1/V2 class, artifact byte, and
   repository method behavior;
6. exact operation dispatch for unchanged
   `BacktestAnalysisRuntime.derive(completed, metric_profile_ref)`: exact existing
   completed inputs produce byte-identical `backtest_analysis@1`; exact verified
   completed-v3 input produces `backtest_analysis@2`; no `derive_v2`, new operation,
   generic wrapper, heuristic manifest unwrap, V2→V1 downgrade, or retry through V1;
7. exact minimal verification fields: immutable root refs/hashes, non-CAS local G12D
   bodies/hashes, fresh recomposed case/full trace/result, comparisons, and no
   duplicated transitive bodies;
8. exact fresh execution-input read, Bundle reopen, PREP, unchanged Resolution,
   composition, verifier execution, and comparison sequence;
9. exact structural/provenance verification that persists comparison mismatch rather
   than rejecting it before Integrity;
10. dedicated same-filesystem proof publication directory and manifest under the
    existing publication root and Run lock, including staging, file/directory fsync,
    exact read-back, hardening, rename, parent fsync, and optional post-publication
    generic-store mirror;
11. exact cooperative operator recovery authority and runbook, with no new recovery
    framework unless this source audit proves code is unavoidable:
    - stop all cooperative writers and establish out-of-band operator exclusivity;
    - derive and inspect only the exact semantic-Run lock, dedicated staging, and final
      paths frozen by this contract; use no glob, age threshold, PID liveness guess,
      broad tree scan, or sibling cleanup;
    - never adopt or rename staging into final;
    - when no final exists and no finalized directory conflicts, remove only the stale
      exact lock and exact scoped staging residue, fsync each mutated staging/run
      parent, then retry through normal `RunPublicationLock` acquisition;
    - when one exact final candidate exists with no conflicting staging/unmanaged
      sibling, remove only the stale exact lock, fsync its parent, and retry; only the
      later lock holder's full exact final-tree verification plus parent fsync may
      accept it idempotently;
    - refuse cleanup when final is malformed, partial, conflicts with staging or
      another scoped final, escapes scope, or cannot be classified exactly; leave it
      unmanaged for operator attention and never auto-delete it;
    - if an operator recovery receipt is recorded, it is operational and noncanonical,
      outside CAS/proof/manifest/Integrity/Result authority. No filesystem path or PID
      is serialized into proof bytes;
12. exact crash-state/failure mapping: stale `.publication.lock` is
    `RUN_LOCK_UNAVAILABLE` / `run_lock_unavailable` during normal execution; staging
    residue is `STAGING_EXISTS` / `staging_exists`; rename-before-parent-fsync is
    absent-or-visible but untrusted from the crashed attempt; an exact visible final
    needs later under-lock verification plus parent fsync; malformed/partial/unmanaged/
    conflicting final never succeeds. Decide exact precedence among current
    `FINAL_DESTINATION_EXISTS`, `PUBLICATION_VERIFICATION_FAILED`, and
    `ATOMIC_FINALIZE_FAILED`, adding one code only if none is semantically exact;
13. exact `CanonicalPublicationManifestV2` canonical-v3 and evaluation-v2 coverage,
    hash preimages, source hashes, IDs, collision/stale/partial handling, and
    acyclicity;
14. exact Resolution-first boundary: development/ineligible Profiles/Build and
    incompatible Environment remain existing Resolution failures; BLOCKED v2 exists
    only if a compatible decision-grade limitation is source-proven reachable;
15. exact FAILED mapping for Attempt mismatch and verifier mismatch, equality path to
    grade, grade firewall, and same-accepted-build claim ceiling;
16. exact repository replay/cache split:
    `load_completed_v3(BacktestCanonicalPublicationRefV2)` uses the existing
    `ArtifactEnvelopeReader` to verify mirrored proof/publication bytes, hashes, and
    static graph only; it makes no current-local-durability claim and gains no root/path
    argument; facade/cache separately verifies the exact local dedicated-proof
    directory while holding `publication_root` and Reader provenance, requires both
    views to bind identically, permits no canonical-v2 fallback, and leaves development
    schema-3 unchanged;
17. exact analysis replay split: `load_analysis` stays V1-only and follows its current
    completed-load behavior; `load_analysis_v2` exact-loads `backtest_analysis@2`, then
    calls `load_completed_v3` for the nominal V2 source and verifies publication ref,
    execution-result hash, grade, and metric-profile links; cross-version refs fail
    closed without heuristic dispatch;
18. exact Backtest candidate write set for Integrity/publication refs/verified
    publications/analysis/derivation/repository/facade/root export and conditional
    runner/private support, plus focused compatibility, recovery, analysis, and
    architecture tests;
19. exact Platform superproject write set and repository boundary:
    `../tests/contracts/backtest-consumer-port-v2.json`,
    `../tests/support/backtest_consumer_port.py`,
    `../tests/architecture/test_backtest_consumer_port.py`, and the `../backtest`
    gitlink only; preserve `../tests/contracts/backtest-consumer-port-v1.json` bytes;
    freeze V1→`load_completed`/`derive`/`load_analysis`, V2→`load_completed_v3`/same
    `derive`/`load_analysis_v2`, and raw-ref terminal/evaluation dispatch;
20. exact six-node commit protocol: one writer and one clean commit per repository
    node; DRP-03 emits the immutable Backtest candidate; DRP-04 emits a separate
    Platform commit pinning exactly that SHA; DRP-05 emits a Backtest docs-only
    Matrix-row-only governance commit binding both SHAs. Platform remains pinned to
    DRP-03 because DRP-05 changes docs/status only;
21. exact additive failure-code catalog and precedence for selected-lane fresh reopen/
    tamper, stale lock, staging residue, safe recovery cleanup/retry, unsafe cleanup
    refusal, exact existing final, rename-before-parent-fsync recovery, malformed/
    partial/unmanaged/conflicting final, local-proof mismatch, repository static-graph
    mismatch, completed/analysis cross-version mismatch, raw-ref-as-v3-completed
    rejection, and ordinary Resolution/FAILED/BLOCKED outcomes; and
22. exact protected API/byte/signature/fixture/directory fingerprints plus one runnable
    acyclic schema/hash-DAG example and cooperative recovery simulations.

Reuse existing Resolution, PREP, Engine/Runner, Run lock, same-filesystem publication
helpers, schema catalog, evidence repository, analysis Runtime, and Platform test-only
consumer support. Generic `ArtifactEnvelopePublisher` may mirror only after dedicated
durable publication; it is not proof authority.

A second repository/resolver/registry/Reader/provider/recovery framework, new Runtime
facade, caller token, public attested-open result, generic finalized result/outcome
wrapper, Builder import, generic mapping, repository root/path argument, Resolution
policy change, raw-ref canonical-v3 success, heuristic version unwrap, or schema
version based only on initiative name is H2. Required exact versioned completed and
analysis values are additive, not permission for a generic wrapper hierarchy.

## H1/H2 decision and status authority

- H1 `CONTRACT_FROZEN`: independently review every item, update only
  `G07-DURABLE-REBUILD-PROOF-V2` in the Acceptance Matrix to `READY`, and mark DRP-01
  Ready in the DAG.
- H2 `CONTRACT_BLOCKED`: record the first immutable conflict in the new Matrix row,
  mark DRP-01..05 STOPPED in the DAG, and emit no code.

The Matrix owns Gate status; the DAG owns node statuses. Accepted historical
`G07 PASSED` is never overwritten or reinterpreted.

## Acceptance

- exact source lines and current SHA-256 values are cited, including publication refs,
  analysis/derivation/verified-completed classes, repository methods, Platform v1
  consumer support, Resolution, and publication-lock/atomic helpers;
- the runnable example reconstructs every ref/hash and both manifests without a cycle;
- field audit proves transitive CAS bodies are not duplicated;
- mismatch example reaches verified observation then FAILED evaluation;
- compatibility fingerprints prove all existing completed/analysis ref construction,
  behavior, methods, exports, and v1/v2 bytes remain exact; V2 completed/analysis
  wires and dispatch are additive only;
- tests freeze lane selection before reopen, no fallback after selected-lane tamper,
  repository-static versus facade-local durability, exact V1/V2 derive/load dispatch,
  every crash/lock/final-tree state and failure code;
- recovery simulations prove exact scoped cleanup/retry and refuse malformed/partial/
  conflicting/escaping cleanup without adopting or deleting final state;
- cross-repository checks prove DRP-04 pins exactly DRP-03 and DRP-05 changes only the
  unique Matrix row while binding both immutable commits;
- independent review finds no grade backdoor, false durability/retention claim,
  unreachable BLOCKED fixture, heuristic unwrap/downgrade, or raw-ref canonical-v3
  success; and
- Markdown/frontmatter/links, source hashes, Matrix/DAG authority, node count and
  acyclicity, repo-specific docs diff, and gitleaks pass.
