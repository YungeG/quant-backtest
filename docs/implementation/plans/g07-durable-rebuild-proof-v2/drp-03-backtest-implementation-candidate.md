---
id: DRP-03
owner: backtest-runtime-implementation
repository: Backtest
status_authority: README.md
produces:
  - one immutable Backtest implementation candidate commit
  - canonical_attempt_ref@2, integrity context/report@2, completed result@3, and manifest@2
  - BacktestCanonicalPublicationRefV2 and load_completed_v3 static replay/cache
  - BacktestAnalysisV2, AnalysisArtifactRefV2, verified completed-v3 input, and load_analysis_v2
consumes:
  - DRP-02 exact private verified observation
  - existing closed Attempt set and execution hash check
  - exact schema-3 local-repository end-to-end fixture
depends_on:
  contract: [DRP-02]
  evidence: [legacy-integrity-analysis-goldens, deterministic-rebuild-verification-v1-golden, attested-schema3-local-run]
  write_conflict: [integrity-publication-ref-repository-facade-analysis]
---

# DRP-03 Backtest implementation candidate

## Vertical outcome

Create one clean Backtest commit that completes all Backtest-owned implementation
required before any Platform write: proof/Integrity/canonical-v3 publication,
versioned nominal ref, repository static replay, facade/cache integration, and
completed-v3→analysis-v2 support. The Acceptance Matrix remains `READY`; this node
edits no Matrix row or Platform file and updates only the DAG README projection to
record DRP-03 accepted-candidate / DRP-04 Ready.

Record the immutable candidate SHA and exact validation evidence for the typed
cross-repository edge into DRP-04. No later Backtest code commit may be silently
substituted for that candidate.

## Integrity and canonical-v3

Add only the changed existing wires required by the parent:

- `canonical_attempt_ref@2`;
- `integrity_evaluation_context@2` and `integrity_report@2`;
- `completed_backtest_result@3`;
- `CanonicalPublicationManifestV2` / `canonical_publication_manifest@2`; and
- `integrity_evaluation_record@2` only because current v1 exact-requires
  `IntegrityReport` and cannot bind report v2 without breaking v1.

Production Resolution has already succeeded before DRP-02. Development/ineligible
Profiles or Build and incompatible Environment remain existing Resolution failures;
this node does not create BLOCKED evaluations for them and does not modify Resolution.
Integrity consumes only the exact DRP-02 read-back observation and closed Attempt set:
Attempt or verifier mismatch maps to FAILED, equality plus a source-proven compatible
limitation maps to BLOCKED, and equality without a blocker maps to decision grade and
canonical-v3. Omit BLOCKED v2 if DRP-00 proves it unreachable. Integrity alone grades;
`deployment_authorized` remains false.

`CanonicalPublicationManifestV2` exact-covers only:

```text
canonical-v3/
  rebuild-verification.json        verification@1
  proof-publication-manifest.json  proof-publication-manifest@1
  canonical-attempt-ref.json       canonical-attempt-ref@2
  integrity.json                   integrity-report@2
  result.json                      completed-result@3
  publication-manifest.json        canonical-publication-manifest@2
```

or:

```text
integrity-evaluations-v2/<id>/
  rebuild-verification.json        verification@1
  proof-publication-manifest.json  proof-publication-manifest@1
  integrity.json                   integrity-report@2
  evaluation-outcome.json          evaluation-record@2
  publication-manifest.json        canonical-publication-manifest@2
```

The first two files are byte-identical to DRP-02's finalized dedicated publication.
No child references the Result or canonical manifest hash. Schema-1 manifest and all
accepted v1/v2 artifacts, constructors, bytes, and layouts remain exact.

## Nominal completed ref, repository replay, and facade/cache

Preserve `BacktestCanonicalPublicationRef` construction, wire, and schema-1 behavior.
Add `BacktestCanonicalPublicationRefV2`, exact over
`canonical_publication_manifest@2`, and add only that completed arm to the existing
`run(request)` return union. Canonical-v3 COMPLETED returns V2; terminal/evaluation
remains raw `ArtifactRef`.

Add `BacktestEvidenceRepository.load_completed_v3(
ref: BacktestCanonicalPublicationRefV2)` while preserving `load_completed()` exact and
V1-only. Reuse the existing repository/catalog/resolver and configured
`ArtifactEnvelopeReader`; verify exact six-artifact coverage, mirrored proof bytes,
all source/hash/ref bindings, transitive immutable bodies, and the full static graph.
This is repository-static verification only, not current local durability, and adds no
root/path argument, second repository, resolver, registry, or graph walker.

`run(request)` selects the lane before fresh reopen only for exact schema 3, requested
decision grade, non-cancellation `run`, exact `LocalMarketBundleReader` type, and
private `open` provenance. Once selected, reopen/tamper failure has no fallback.
Canonical-v1/v2 is not an attested hit or downgrade. Cache success requires both exact
current dedicated-proof final-tree verification under the Run lock and valid
`load_completed_v3` static replay, bound to identical proof bytes/hashes. Development
schema-3 remains canonical-v2.

## Additive completed-v3 analysis compatibility

Canonical-v3 must remain analysis-ready without changing any existing analysis class,
ref, artifact bytes, public signature, or method behavior. Freeze and implement the
minimum additive V2 analysis surface selected by DRP-00:

- `BacktestAnalysisV2`, stored only as `backtest_analysis@2`, with the same accepted
  metric semantics and an exact `BacktestCanonicalPublicationRefV2` source;
- `AnalysisArtifactRefV2`, exact only over `backtest_analysis@2`;
- `VerifiedBacktestAnalysisV2`, the exact loaded V2 view;
- `VerifiedCompletedPublicationV3`, the minimum verified canonical-v3 input returned
  by `load_completed_v3`; and
- `BacktestEvidenceRepository.load_analysis_v2(
  ref: AnalysisArtifactRefV2) -> VerifiedBacktestAnalysisV2`.

`BacktestAnalysisRuntime.derive(completed, metric_profile_ref)` keeps its exact name,
parameters, and operation. Exact existing completed inputs continue to produce the
same `BacktestAnalysis` / `AnalysisArtifactRef` schema-1 bytes. Exact
`VerifiedCompletedPublicationV3` dispatches to `BacktestAnalysisV2` /
`AnalysisArtifactRefV2`. There is no `derive_v2`, no new operation, no generic union
wrapper, no manifest inspection to guess a version, and no V2→V1 unwrap or downgrade.
Unknown or mismatched exact types fail through the DRP-00-frozen typed disposition.

The V2 analysis repository replay exact-loads the V2 analysis and metric profile,
then calls `load_completed_v3` for its nominal source and verifies publication ref,
execution-result hash, and grade links. It never routes a V2 analysis through
`load_analysis` or a canonical-v3 completed ref through `load_completed`.

## Cooperative recovery integration

Publication and cache paths preserve the DRP-00 operator authority. Runtime performs
no stale-lock breaking or automatic staging/final cleanup. After the operator's exact
scoped safe cleanup and retry, normal `RunPublicationLock` acquisition applies. A
visible exact final is accepted only by a later holder after full under-lock final-tree
verification and successful parent fsync. Malformed, partial, simultaneous conflicting,
or otherwise unmanaged final state fails closed and remains for operator attention.
An optional recovery receipt is operational and noncanonical; it is outside CAS,
manifests, verification, Integrity, Result, and Matrix artifact hashes. Filesystem
paths and PIDs never enter proof bytes.

## End-to-end acceptance

One exact local G12D fixture proves:

```text
run(schema-3 requested decision grade)
→ exact configured repository-open Local Reader
→ existing Resolution
→ two finalized Attempts/full traces
→ fresh reopen/PREP/Resolution/case/rebuild
→ durable verification@1 + proof-publication-manifest@1
→ exact final read-back
→ Integrity v2
→ atomic canonical-v3 manifest@2
→ BacktestCanonicalPublicationRefV2
→ exact current local dedicated-proof verification
→ load_completed_v3(V2)
→ BacktestAnalysisRuntime.derive(verified completed v3, metric profile)
→ AnalysisArtifactRefV2
→ load_analysis_v2(V2)
→ canonical-v3 cache hit with zero new Attempt/rebuild
```

Acceptance also requires:

- mismatch durable observation followed by FAILED; reachable-only BLOCKED policy;
- exact comparison/hash/layout and static/local split mutation coverage;
- direct/in-memory/arbitrary/subclass Reader rejection and no selected-lane fallback;
- safe cleanup/retry and unsafe cleanup refusal simulations inherited from DRP-02;
- V1 analysis/publication constructors, refs, bytes, signatures, derive/load behavior,
  package exports, and Platform v1 fixture hash fingerprints unchanged;
- exact-type tests proving V1 and V2 derive dispatch with no heuristic unwrap;
- focused and full Backtest suites, architecture/import checks, static checks,
  diff-check, and gitleaks; and
- the same candidate commit updates only the DAG README projection from DRP-03 blocked /
  DRP-04 blocked to DRP-03 accepted-candidate / DRP-04 Ready; and
- a clean Backtest working tree after creating one candidate commit.

The node's acceptance record must name the immutable candidate SHA consumed by DRP-04.
It does not update the Matrix row to `PASSED`.
