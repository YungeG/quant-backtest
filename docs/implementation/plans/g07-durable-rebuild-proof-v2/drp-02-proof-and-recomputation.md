---
id: DRP-02
owner: backtest-runtime-rebuild-verifier
status_authority: README.md
produces:
  - deterministic_rebuild_verification@1
  - deterministic_rebuild_verification_publication_manifest@1
  - exact private read-back verified observation
consumes:
  - DRP-00 H1 verification/publication contract
  - DRP-01 private Local Reader reopen contract
  - schema-3 execution input and two finalized Attempts
depends_on:
  contract: [DRP-00-H1, DRP-01]
  evidence: [schema3-prep-two-attempt-full-trace-fixture]
  write_conflict: [execution-rebuild-proof-publication]
---

# DRP-02 durable verification observation and independent recomputation

## Vertical outcome

After successful production Resolution and exactly two finalized
READY_FOR_INTEGRITY Attempts, independently recompute once, construct the minimal
`deterministic_rebuild_verification@1`, publish it with its exact schema-1 dedicated
proof-publication manifest under the existing publication root and held Run lock, read
back the final tree, and return only the DRP-00-frozen private verified value.

This node is orchestration plus exact codec/comparison/publication logic. It is not a
second Runner, repository, resolver, Reader, policy framework, public facade, or public
proof constructor.

## Required sequence

1. Accept only the lane already selected from exact schema 3, requested decision
   grade, exact Local Reader type, and presence of DRP-01 provenance, plus two finalized
   eligible Attempts; do not reselect or downgrade the lane.
2. Freshly read and exact-decode the execution-input ArtifactRef.
3. Freshly reopen the Local Bundle and compare exact current G12D publication,
   retention, manifest, stream bodies/hashes, and retrievability.
4. Replay PREP and unchanged Resolution; compare immutable roots.
5. Recompose target stream, semantic spec, identity manifest, and case.
6. Execute one verifier-owned full-trace rebuild without a third Attempt identity.
7. Compute exact comparisons and first divergences between both Attempts and the fresh
   rebuild.
8. Construct only the minimal root refs/hashes, required non-CAS G12D bodies/hashes,
   and fresh rebuild observation frozen by DRP-00.
9. Publish `verification.json` plus
   `proof-publication-manifest.json` through dedicated same-filesystem
   staging→file fsync→exact verify→harden→rename→final verify→parent fsync.
10. Exact-decode the final directory, reconstruct all roots, resolve transitive bodies,
    and return the private verified observation.

Generic artifact-store mirroring may occur afterward but is never durability authority.
Normal execution follows the existing cooperative lock policy exactly: a stale
`.publication.lock` is `RUN_LOCK_UNAVAILABLE` / `run_lock_unavailable` and staging
residue is `STAGING_EXISTS` / `staging_exists`; Runtime performs no stale-lock break,
staging adoption, or automatic final cleanup.

DRP-00's cooperative operator runbook is the sole recovery authority. After a process
crash, operators stop all writers and establish exclusivity, inspect only the exact
semantic-Run lock/staging/final paths, and never adopt staging. With no final conflict,
they remove only the stale exact lock and exact scoped staging residue, fsync every
mutated parent, and retry through normal `RunPublicationLock`. With one exact final
candidate and no staging/unmanaged conflict, they remove only the stale exact lock,
fsync its parent, and retry; only the later lock holder's full exact final-tree
verification plus parent fsync may accept it idempotently. Malformed, partial,
escaping, simultaneous, or conflicting final state makes cleanup refuse mutation and
remains unmanaged for operator attention; final is never auto-deleted. Any recovery
receipt is operational/noncanonical and outside proof authority, and no path or PID
enters proof bytes.

## Mismatch and failure boundary

Attempt mismatch or fresh-rebuild mismatch is valid observed evidence. Persist and
read it back with exact comparison fields; DRP-03 maps it to FAILED. Do not require
semantic equality to construct or verify the observation.

Pre-Integrity failure is only inability to enter the single Run lock, acquire/decode/
freshly reopen/recompute, structurally construct, durably publish, or read back. Fresh reopen
or tamper failure after lane selection never falls back. Staging and orphan mirror
content are never recognized as finalized. A visible rename-before-parent-fsync final
is untrusted from the crashed attempt and is recognized only by the later normal
under-lock exact-verification-plus-parent-fsync rule above. A fully finalized
observation may remain if a later Integrity step fails; it is not a canonical Result.

The observation states only same-accepted-build reproducibility from currently
retrievable immutable local inputs and contains no grade, qualification, live, or
deployment field.

## Acceptance

- additive goldens round-trip both schema-1 artifacts and all hash/source/ref bindings;
- equality and mismatch fixtures both produce structurally verified durable
  observations; mismatch carries exact per-Attempt results/first divergence;
- mutation table covers every root, current G12D body/hash, stale/cross-run/bundle/
  build evidence, Attempt order, trace/result mismatch, and Reader substitution;
- crash/recovery simulations cover stale lock, staging non-adoption, child fsync,
  verification, hardening, rename, absent/visible rename-before-parent-fsync outcomes,
  operator exclusivity, exact scoped lock/staging cleanup plus parent fsync and normal
  retry, later exact idempotent acceptance, and refusal to mutate malformed/partial/
  escaping/simultaneous/conflicting final state with exact frozen codes;
- counters prove fresh input read, reopen, PREP, Resolution, composition, and execution;
- field audit proves no redundant transitive CAS body duplication;
- legacy schema-3 hydration/PREP behavior remains unchanged; and
- the same commit updates only the DAG README projection from DRP-02 blocked / DRP-03
  blocked to DRP-02 accepted / DRP-03 Ready.
