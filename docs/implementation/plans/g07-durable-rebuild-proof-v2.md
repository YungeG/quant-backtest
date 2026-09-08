---
id: G07-DURABLE-REBUILD-PROOF-V2
status_authority: ../acceptance-matrix.md
owner: backtest-runtime
base_commit: 3ad3c42a971988db6712aff507ec630c90c0ea1e
execution_dag: g07-durable-rebuild-proof-v2/README.md
produces:
  - deterministic_rebuild_verification@1
  - deterministic_rebuild_verification_publication_manifest@1
  - canonical-v3 decision-grade publication and BacktestCanonicalPublicationRefV2
  - additive static repository replay plus facade-owned local durability verification
  - additive canonical-v3 completed-to-analysis V2 compatibility
consumes:
  - schema-3 backtest_execution_input_bundle
  - exact local G12D Bundle publication and retention bodies
  - PREP replay and two finalized Attempts
  - existing Resolution, Runner, Integrity, publication root, Run lock, and evidence repository
---

# G07 durable deterministic rebuild/retention proof v2

## Outcome

Add one durable verifier-owned observation lane for decision-grade Backtest execution
without changing or reinterpreting accepted v1/v2 APIs, constructors, canonical bytes,
fixtures, directories, Results, publication meanings, or development behavior.

`BacktestRuntime.run(request)` remains the sole public facade. An exact schema-3
request that already asks for `RequestedResultGrade.DECISION_GRADE` selects the new
lane before any fresh reopen only when the Runtime's configured market reader has the
exact `LocalMarketBundleReader` type and the private repository-open provenance that
only existing `open` retains. A later fresh reopen or tamper failure is a pre-Integrity
failure with no legacy fallback. `run_with_cancellation`, development requests, legacy
requests, and schema-3 requests using any other Reader retain their current behavior.
No `run_attested_v3` or other public Runtime method is added.

The [Acceptance Matrix](../acceptance-matrix.md) is the sole Gate-status authority and
records this initiative as `READY — DRP-00 CONTRACT_FROZEN`. The
[execution DAG](g07-durable-rebuild-proof-v2/README.md) owns DRP node execution
statuses. DRP-00 is `ACCEPTED_H1` and DRP-01 is the sole Ready node. The six-node route
creates one immutable Backtest implementation candidate, one separate Platform
consumer-v2 commit pinning that exact candidate, and one final Backtest Matrix-row plus
DAG-status docs-only governance commit.

## Problem bound at base HEAD

These facts are frozen against base commit
`3ad3c42a971988db6712aff507ec630c90c0ea1e`:

| Authority | SHA-256 | Bound fact |
| --- | --- | --- |
| [`integrity.py`](../../../packages/backtest-runtime/src/crypto_quant_backtest/integrity.py) | `sha256:bcb7030666367a9600077d50d6abf132cc12e0f11cdd7a3c23d8f2a6306872c5` | Lines 240–305 define caller-supplied `DeterministicRebuildEvidence` schema 1 with optional proof hashes; lines 629–654 test only non-null presence. |
| [`facade.py`](../../../packages/backtest-runtime/src/crypto_quant_backtest/facade.py) | `sha256:df38483bb7b752d2b13a814e48ddf09a32735c83f2a5baed3892ee84384ac436` | `BacktestRuntime` exposes only `run` and `run_with_cancellation`; its constructor already receives one `market_reader` and one `publication_root`. Lines 870–895 construct v1 evidence with both proof hashes `None`. |
| [`execution_inputs.py`](../../../packages/backtest-runtime/src/crypto_quant_backtest/execution_inputs.py) | `sha256:66344060f875218dbf2cd2115fc7885da7ab35016ee72d58550d60af0c2a17c5` | Lines 2634–2686 register exact schema-3 decoding; lines 3385–3479 freshly read, bind, and decode its ArtifactEnvelope. |
| [`local_market_bundle_reader.py`](../../../packages/market-data-contracts/src/crypto_quant_market_data/local_market_bundle_reader.py) | `sha256:bbca532a90789590b882fc3e9a259cce0bfbcb8c37bef6b97ee946f3e0b7a57a` | `open` verifies the exact local G12D tree, manifest, publication, retention body, stream coverage, payload hashes, read-only tree, and current retrievability, but returns a Reader retaining none of that repository provenance. The public constructor accepts only an in-memory delegate. |
| [`resolution.py`](../../../packages/backtest-runtime/src/crypto_quant_backtest/resolution.py) | `sha256:b984e1e0a816154dc85e2c399156ea539a64834bac695129efba5f6843036d44` | Resolution rejects incompatible environments and requested decision-grade use of development/ineligible Profiles or Build before a `ResolvedBacktestRequest` exists. Compatible decision-grade environments may still carry explicit limitations. |
| [`_publication.py`](../../../packages/backtest-runtime/src/crypto_quant_backtest/_publication.py) | `sha256:6855e2cef8bf7a6df3d7cbf70694cd6094152d72f440c353cb1c487450903986` | The existing cooperative Run lock and same-filesystem helpers provide file fsync, read-only hardening, directory verification, rename support, and directory fsync primitives; DRP-00 must freeze the exact dedicated proof sequence. |
| [`runner.py`](../../../packages/backtest-runtime/src/crypto_quant_backtest/runner.py) | `sha256:4ebfa969e88cd4485e60f92a3fc052230c662f404e429842ed55b5a9603e17b5` | Lines 627–655 and 659 onward bind current canonical-v2 cache/layout behavior. |
| [`evidence_repository.py`](../../../packages/backtest-runtime/src/crypto_quant_backtest/evidence_repository.py) | `sha256:617347b75b03c9717448e11dfa5a1d6c23503db1840b8c84c2fd28fa9d860e7d` | `load_completed()` accepts the schema-1 canonical publication ref and exact current canonical-v2 graph. |
| [`publication_refs.py`](../../../packages/backtest-runtime/src/crypto_quant_backtest/publication_refs.py) | `sha256:89782d266ceae919118310a94ff6075925e3c408d2595833b93d9562865dcd00` | `BacktestCanonicalPublicationRef` nominally and exactly requires `canonical_publication_manifest@1`; `RunPublicationRef` is currently that completed ref or the non-nominal raw `ArtifactRef` arm used by terminal/evaluation outcomes, so raw refs cannot carry the required canonical-v3 COMPLETED nominal semantics. |
| [`BT-PORT-01` v1 fixture](../../../../tests/contracts/backtest-consumer-port-v1.json) | `sha256:5f9971573154a92aa83f6ac6edbb36024721ad5b54a35f0f14414c1e393f69fa` | The frozen Platform-facing v1 contract recognizes only schema-1 nominal completed/analysis refs and the operations `run`, `derive`, `load_completed`, `load_terminal`, and `load_analysis`; additive Platform version dispatch is required without editing or reinterpreting this fixture. |
| [`Platform` v1 consumer support](../../../../tests/support/backtest_consumer_port.py) | `sha256:031a27f1231b0579c6852ea94cc510a9cdf07fa5a3453330b3ac0dba0176ad67` | The Platform superproject test-only consumer exact-validates only schema version 1 refs and routes one `derive` operation through `load_completed` and `load_analysis`; v2 must remain additive and exact-dispatching. |
| [`analysis.py`](../../../packages/backtest-runtime/src/crypto_quant_backtest/analysis.py) | `sha256:187fd00f6248cd1c8ea71cc7b0ee62c0f14909e51bb5ff7a49e0bacf80269bcb` | `BacktestAnalysis`, `AnalysisArtifactRef`, and `VerifiedBacktestAnalysis` are exact schema-1 contracts whose source publication ref is exact `BacktestCanonicalPublicationRef`; they cannot bind canonical-v3 without additive V2 types. |
| [`analysis_derivation.py`](../../../packages/backtest-runtime/src/crypto_quant_backtest/analysis_derivation.py) | `sha256:de18451735edf8a05edbed6d8aeb65f1ea6d8ca0518478eb878b5b5897fe9a96` | `BacktestAnalysisRuntime.derive` is already the sole analysis operation and exact-dispatches current verified completed inputs to schema-1 analysis. Canonical-v3 support must extend this same operation without a new method or downgrade. |
| [`verified_publications.py`](../../../packages/backtest-runtime/src/crypto_quant_backtest/verified_publications.py) | `sha256:7a3380d9129fb4845fdd770cc4b70fc5c3852dff580796a952164326c3043796` | Existing verified completed views retain a schema-1 nominal source publication ref; canonical-v3 needs one additive minimum verified completed-v3 input while preserving both current classes. |
| [`CanonicalPublicationManifest`](../../../packages/backtest-runtime/src/crypto_quant_backtest/integrity.py) | covered by `integrity.py` hash above | Schema 1 exact-covers only the three current canonical children or two current evaluation children; its entry type rejects schema versions other than 1, except completed Result schema 2. It cannot represent canonical-v3 children. |
| [Integrity fixtures](../../../tests/runtime/integrity/_fixtures.py) | `sha256:e1e086821590f999d23f4ce38ca370d01ab8b6b5c828b81beb251f826baf2fcb` | Current fixtures manufacture opaque retention/rebuild hashes rather than resolving proof bodies. |
| [ADR 0008](../../adr/0008-source-bounded-decision-grade.md) | `sha256:a213f151393d23e264eaf90de5d6ac7a556548de84c420a3cb5a5bb703f3c3a8` | Naked hashes and caller booleans cannot qualify; Integrity remains grade authority. |
| [accepted G12M prerequisite decision](../../research/g12m-tushare-fixed-singleton-prerequisite-authority-v1.md) | `sha256:60a74445d4d6691e8cf138830b464f8b927a164e9f330c9ba00329fcbb0ee611` | The generic durable proof prerequisite is independently missing; this plan does not change the accepted H2 receipt. |

Existing Attempts and canonical-v2 remain useful immutable inputs, but do not prove a
fresh verifier-owned reopen and rebuild. Hashes and booleans are links or observations,
not authority by themselves.

## Frozen additive contract

DRP-00 freezes exact field spelling, private symbol spelling, and failure codes. H1
must preserve every semantic rule below; otherwise it records H2.

### 1. Sole facade and dispatch boundary

- Add no public Runtime method. `run(request)` selects the new lane only for an exact
  schema-3, requested-decision-grade request, no cancellation, and an exact configured
  `LocalMarketBundleReader` carrying repository-open provenance frozen by DRP-00.
- The request remains caller-authored. Runtime never upgrades requested grade.
- `run_with_cancellation` is unchanged and never enters this lane.
- Development schema-3 `run()` remains canonical-v2. Schema 1/2 and legacy behavior
  remain exact.
- In-memory Readers, arbitrary protocol Readers, Local Reader subclasses, and a
  directly constructed `LocalMarketBundleReader` do not attest. Direct construction
  has no repository-open provenance and remains on the current non-attested/blocked
  path. Lane selection uses only exact schema 3, requested decision grade, exact Local
  Reader type, and presence of the private provenance; it performs no fresh reopen.
- Once the new lane is selected, a fresh reopen or tamper failure is pre-Integrity and
  canonical-v2 is never a cache hit, fallback, mirror, or downgrade. Existing
  canonical-v1/v2 state cannot be rewritten or upgraded.
- Preserve `BacktestCanonicalPublicationRef` construction, wire bytes, and schema-1
  behavior. Add the versioned nominal `BacktestCanonicalPublicationRefV2`, exact over
  only `canonical_publication_manifest@2`. `run(request)` keeps its exact parameters
  and sole-facade role; its return union gains only this V2 completed ref. Canonical-v3
  COMPLETED returns V2, while terminal and evaluation outcomes remain raw
  `ArtifactRef`. Raw `ArtifactRef` must never represent canonical-v3 success.

### 2. Minimal Local Reader provenance seam

Preserve `LocalMarketBundleReader.__init__(delegate)`,
`LocalMarketBundleReader.open(*, repository_root, bundle_ref)`, Reader protocol
methods, `__all__`, and package-root exports.

`open` may retain only the smallest private state needed to prove that this exact
instance came from the verified repository open: normalized absolute repository root,
exact Bundle ref, and the verified G12D publication/retention values needed for a
fresh read. The direct constructor leaves this state absent.

Add one exact versioned package-internal read/reopen interface on the existing concrete
class. DRP-00 freezes its spelling, exact private process value, and exact-type checks.
The interface freshly executes the existing `open` verification and returns the
reopened Reader plus exact decoded publication/retention bodies and hashes. It is not
a root export, public token, new `LocalMarketBundleAttestedOpenV2`, protocol, registry,
Reader framework, or caller-constructible authority object.

The claim is limited to repository provenance in a cooperative Python process. It is
not a sandbox, trusted-root identity claim, or defense against a caller copying a
valid tree and opening that copy.

### 3. Artifact and wire-version catalog

The initiative remains named v2, but each new artifact type starts at schema 1:

| Artifact/value | Version rule |
| --- | --- |
| `deterministic_rebuild_verification` | new artifact type, schema 1 |
| `deterministic_rebuild_verification_publication_manifest` | new exact proof-publication root type, schema 1 |
| `canonical_attempt_ref` | additive schema 2 because it changes the existing wire to bind verification and its durable publication root |
| `integrity_evaluation_context` / `integrity_report` | additive schema 2 |
| `completed_backtest_result` | additive schema 3 |
| `canonical_publication_manifest` / `CanonicalPublicationManifestV2` | additive schema 2 with exact canonical-v3 and evaluation-v2 layouts; schema 1 unchanged |
| `BacktestCanonicalPublicationRefV2` | additive nominal completed-publication ref that exact-wraps only `canonical_publication_manifest@2`; V1 constructor/wire/behavior unchanged |
| `VerifiedCompletedPublicationV3` | additive minimum verified canonical-v3 input returned by `load_completed_v3`; current verified completed V1/V2 classes unchanged |
| `BacktestAnalysisV2` / `backtest_analysis` | additive schema 2, exact over a V2 completed publication source; `BacktestAnalysis` schema 1 unchanged |
| `AnalysisArtifactRefV2` / `VerifiedBacktestAnalysisV2` | additive exact schema-2 analysis ref/loaded view; V1 ref/view unchanged |
| `integrity_evaluation_record` | additive schema 2 only because current v1 exact-requires `IntegrityReport`; a v2 report cannot be represented without breaking that exact-type contract |

No `FinalizedCanonicalResultV3`, `FinalizedIntegrityEvaluationV2`, generic versioned
outcome wrapper, or schema version justified only by the initiative name is added.
Public additions are limited to the exact nominal completed and analysis values needed
for canonical-v3 replay and derivation. DRP-00 must reuse existing process/repository
abstractions where their exact contracts permit; any other unavoidable verified
process value stays package-private.

### 4. Minimal verification body

`deterministic_rebuild_verification@1` binds immutable roots rather than duplicating
every transitive body already resolvable through ArtifactRefs/CAS. DRP-00 freezes the
exact minimum fields, including:

1. semantic Run, normalized request, resolved Environment/Profile/Build root hashes,
   and the exact schema-3 execution-input ArtifactRef/source identity;
2. the two finalized Attempt evidence-manifest ArtifactRefs, publication/source
   identities, and `AttemptExecutionHash` roots;
3. PREP, target stream, semantic spec, identity manifest, case, trace, and result root
   refs/hashes where those bodies already have an immutable resolver path;
4. exact current local G12D `market_bundle_publication@1` and
   `MarketBundleRetentionProofV1` bodies plus their hashes, because these are not CAS
   children, together with successful fresh retrievability under the same cooperative
   filesystem model; and
5. the fresh verifier-owned recomposed case, full trace, execution result and hashes,
   plus exact per-Attempt comparison results and first-divergence subjects.

The verifier and repository resolve and exact-decode transitive bodies. The
verification does not copy resolved request, Build, PREP, case, both Attempt manifests,
both traces, and both results wholesale merely because they are available.

The local retention observation says only that the exact current G12D publication and
retention bodies/hashes were verified and their referenced local files were retrievable
at verification time. It does not assert future policy compliance, trusted root
identity, remote durability, adversarial tamper resistance, or protection against a
copied valid tree.

No verification field can set grade, qualification, live authorization, provider
status, or deployment authorization.

### 5. Fresh recomputation and mismatch observation

After Resolution succeeds and two ordinary finalized Attempts exist, the verifier:

1. freshly reads and exact-decodes the schema-3 execution-input ref;
2. freshly reopens the configured Local Reader through its retained repository-open
   provenance and rechecks the exact current G12D tree/bodies/hashes;
3. reruns PREP and compares its immutable root;
4. reruns unchanged Resolution and compares request, Environment, Profile, Build, and
   compatibility roots;
5. recomposes target stream, semantic spec, identity manifest, and case;
6. executes one verifier-owned full-trace rebuild outside the two Attempt identities;
   and
7. records exact comparison results against each Attempt and between the Attempts.

Semantic equality is not a prerequisite to durable observation. If either Attempts
mismatch or the verifier rebuild mismatches either Attempt, DRP-02 still publishes and
read-back verifies the structurally and provenance-valid
`deterministic_rebuild_verification@1`. Integrity v2 consumes that exact verified
observation and emits a FAILED evaluation. Full equality may proceed to ordinary
Integrity grading.

Pre-Integrity failure is limited to inability to acquire, exact-decode, reopen,
recompute, structurally construct, durably persist, or read back the observation.
Comparison inequality is evidence, not proof-production failure.

The claim ceiling is **same-accepted-build reproducibility from currently retrievable
immutable local inputs**. It is not diverse-implementation, compiler, hardware, or
adversarial-build independence.

### 6. Dedicated durable publication

Generic `ArtifactEnvelopePublisher.put`/`ArtifactEnvelopeReader.read` is not the
durability authority. Under the existing `publication_root` and held
`RunPublicationLock`, DRP-02 uses a dedicated same-filesystem publisher with an exact
DRP-00-frozen relative directory containing:

```text
verification.json                  deterministic_rebuild_verification@1
proof-publication-manifest.json    deterministic_rebuild_verification_publication_manifest@1
```

The publisher writes a sibling staging directory, fsyncs each file, exact-decodes and
verifies child/source/hash/coverage bindings, hardens files and directory read-only,
renames on the same filesystem, verifies the final tree, and fsyncs the parent. It then
reads the final directory back through its exact decoder before returning the private
verified process value.

A process crash may leave `.publication.lock`; normal execution fails closed as
`RUN_LOCK_UNAVAILABLE` (`run_lock_unavailable`) and performs no automatic recovery.
DRP-00 freezes the sole cooperative operator runbook: stop all writers and establish
operator exclusivity; inspect only the exact scoped lock/staging/final paths; never
adopt staging; when no final conflict exists, remove only the stale exact lock and
exact scoped staging residue, fsync every mutated parent, then retry under the normal
Run lock. With one exact final candidate and no staging/unmanaged conflict, remove only
the stale lock, fsync its parent, and retry; only the later holder's full under-lock
final-tree verification plus parent fsync may accept it idempotently. Malformed,
partial, escaping, simultaneous, or conflicting final state makes cleanup refuse
mutation, remains unmanaged for operator attention, and is never auto-deleted.

Any recovery receipt is operational/noncanonical and outside CAS, proof, manifests,
Integrity, Result, and grade authority. No filesystem path or PID enters proof bytes.
Staging residue remains `STAGING_EXISTS` (`staging_exists`) during normal execution.
DRP-00 freezes exact code precedence; no catch-all, implicit cleanup, or new recovery
framework is permitted unless DRP-00 proves existing cooperative operations cannot
express the required safe procedure.

Once the dedicated publication completes, it may remain as a durable observation if a
later Integrity/publication step fails; it is not a completed Run. Generic
artifact-store mirroring may occur afterward for transport or existing resolver
convenience, but mirror success is neither the durability claim nor the root of trust.

### 7. Resolution, Integrity, and honest outcomes

Production Resolution runs before Attempts, proof publication, or Integrity. Existing
policy rejects development/ineligible Profiles, development/ineligible Build, and
incompatible inputs as the current `backtest_resolution_failure@1`; none is required
to manufacture a v2 BLOCKED evaluation, and this plan does not modify Resolution.

Integrity v2 consumes only the exact read-back verified observation and the closed
Attempt set. It rechecks bindings and maps:

- Attempt execution-hash mismatch or verifier rebuild mismatch to FAILED;
- full comparison equality plus a compatible decision-grade environment with a
  genuinely reachable explicit limitation to BLOCKED under existing Integrity
  limitation policy; and
- full equality with no blocking issue to decision grade and canonical-v3.

If DRP-00 proves no compatible post-Resolution BLOCKED condition is reachable without
changing policy, BLOCKED v2 is removed from implementation scope. It may not be kept
using development Profile/Build or incompatible Environment fixtures.

Integrity remains the sole grade authority. The observation cannot qualify a provider,
set requested/result grade, or authorize live/deployment use; `deployment_authorized`
remains false.

### 8. CanonicalPublicationManifestV2 and hash DAG

Schema-1 `CanonicalPublicationManifest` remains byte/API exact. Add
`CanonicalPublicationManifestV2` / `canonical_publication_manifest@2` with exact
allowed child schemas and exact coverage for only these layouts.

Successful `canonical-v3` contains:

```text
rebuild-verification.json          deterministic_rebuild_verification@1
proof-publication-manifest.json    deterministic_rebuild_verification_publication_manifest@1
canonical-attempt-ref.json         canonical_attempt_ref@2
integrity.json                     integrity_report@2
result.json                        completed_backtest_result@3
publication-manifest.json          canonical_publication_manifest@2
```

A FAILED or genuinely reachable BLOCKED evaluation-v2 contains:

```text
rebuild-verification.json          deterministic_rebuild_verification@1
proof-publication-manifest.json    deterministic_rebuild_verification_publication_manifest@1
integrity.json                     integrity_report@2
evaluation-outcome.json            integrity_evaluation_record@2
publication-manifest.json          canonical_publication_manifest@2
```

The verification and proof-publication-manifest files are byte-identical to the
read-back dedicated durable publication. The acyclic direction is:

```text
immutable input/Attempt refs + exact local G12D bodies + fresh rebuild observation
                                  ↓
              deterministic_rebuild_verification@1
                                  ↓
 deterministic_rebuild_verification_publication_manifest@1
                     ┌────────────┴────────────┐
                     │ equality                │ mismatch
                     ↓                         ↓
       canonical_attempt_ref@2        integrity context/report@2
                     ↓                         ↓
       integrity context/report@2      evaluation record@2 FAILED
                     ↓                         ↓
 completed_backtest_result@3          publication manifest@2
                     ↓
 canonical_publication_manifest@2
```

No child references Result or canonical publication-manifest hash. The schema-2
canonical manifest is the root of each canonical/evaluation directory; the dedicated
proof-publication manifest remains the earlier durability root for the observation.

### 9. Repository replay and cache

Add `BacktestEvidenceRepository.load_completed_v3(
ref: BacktestCanonicalPublicationRefV2)`. `load_completed()` remains exact and V1-only.
No repository constructor, root/path argument, or second repository is added.

The v3 replay path uses the same `ArtifactEnvelopeReader`, repository catalog, and
resolver machinery. From mirrored canonical proof/publication bytes it can verify
schema-2 exact coverage, hashes, static graph reconstruction, transitive immutable
bodies, and every verification→Attempt-ref→Integrity→Result→manifest binding. It
cannot independently prove current local filesystem durability or inspect the
publisher's dedicated proof directory because it has neither `publication_root` nor
Local Reader provenance. It returns the minimum exact
`VerifiedCompletedPublicationV3` frozen by DRP-00; no second graph walker or generic
finalized result wrapper is added.

Additive analysis replay uses `BacktestAnalysisRuntime.derive` as the same operation
for all accepted versions. Existing verified completed inputs still produce the exact
schema-1 `BacktestAnalysis` / `AnalysisArtifactRef`; exact
`VerifiedCompletedPublicationV3` produces `BacktestAnalysisV2` /
`AnalysisArtifactRefV2`. `load_analysis_v2` exact-loads schema 2 and binds its nominal
V2 source through `load_completed_v3`. `load_analysis` remains V1-only. There is no
`derive_v2`, heuristic unwrap, cross-version retry, or downgrade.

For a run-selected decision-grade schema-3 lane, facade/cache success requires both
(1) exact current local dedicated-proof directory verification while the facade has
`publication_root` and Reader provenance and (2) `load_completed_v3` static graph
replay through the existing repository. The two views must bind to identical proof and
publication bytes/hashes. Missing, stale, partial, or corrupt state fails closed.
Canonical-v2 is not a fallback or attested cache hit. Existing development schema-3
cache behavior remains canonical-v2.

### 10. Six-node cross-repository fan-in

The execution graph has exactly six nodes and one writer/clean commit per node and
repository. DRP-01 and DRP-02 retain their vertical provenance/proof outcomes. DRP-03
combines Integrity/publication with ref/repository/facade/analysis integration to
produce one immutable Backtest implementation candidate while the Matrix remains
`READY`. DRP-04 runs only in the Platform superproject, changes the exact `../` write
set, and creates a separate commit whose `backtest` gitlink equals exactly the DRP-03
SHA. Typed cross-repository edges carry that immutable candidate, the exact gitlink,
consumer-v2 contract results, and both commit SHAs.

DRP-05 returns to Backtest and changes only the unique Matrix row plus the DAG README's
DRP-04/DRP-05 status projection in one docs-only governance commit. It binds both
immutable commits and records final evidence before atomically setting the row to
`PASSED` and closing those node statuses. Platform remains correctly pinned to the DRP-03
code commit because DRP-05 changes no code, fixture, public byte, operation, or
consumer behavior. No node mixes Backtest submodule and Platform superproject writes.

## Rejection matrix

| Rejected input/state | Required disposition |
| --- | --- |
| caller proof hash/boolean/mapping, v1 rebuild evidence, or arbitrary ref | no attested authority |
| direct/in-memory/arbitrary/subclass Reader or exact Local Reader without private `open` provenance | existing non-attested/current blocked path only; never new lane |
| selected lane then fresh reopen/tamper, execution-input, Bundle, G12D body, PREP, Resolution, case, ref/body/source, or persistence failure | pre-Integrity failure; no legacy fallback, v2 evaluation, or canonical-v3 |
| Attempt mismatch or verifier rebuild mismatch after a valid durable observation | Integrity v2 FAILED evaluation |
| development Profile/Build or incompatible environment | existing pre-Attempt Resolution failure |
| compatible decision-grade environment with explicit blocking limitation | BLOCKED only if DRP-00 confirms reachability under current policy |
| existing canonical-v1/v2 only after new lane selected | no hit, fallback, rewrite, or downgrade |
| stale `.publication.lock` after crash | normal execution returns `RUN_LOCK_UNAVAILABLE` / `run_lock_unavailable`; operator recovery requires stopped writers, exclusivity, exact scoped inspection, parent fsync, then normal-lock retry |
| staging residue without final conflict | `STAGING_EXISTS` / `staging_exists` during execution; never adopted; operator may remove only exact scoped residue under the frozen runbook and fsync its parent |
| exact final directory visible after rename-before-parent-fsync | not trusted from the crashed attempt; operator removes only stale lock, then a later normal holder must full-verify under lock and fsync parent before idempotent acceptance |
| malformed, partial, escaping, simultaneous, unmanaged, or conflicting dedicated/canonical/evaluation final directory | recovery refuses mutation; operator attention; DRP-00 freezes exact precedence among `FINAL_DESTINATION_EXISTS`, `PUBLICATION_VERIFICATION_FAILED`, and `ATOMIC_FINALIZE_FAILED` (and an additive code only if none is semantically exact); never auto-deleted or successful |
| V2 completed or analysis ref sent through a V1 repository method, or unknown version | exact typed/version failure; no heuristic unwrap, retry, or downgrade |
| raw `ArtifactRef` carrying `canonical_publication_manifest@2` | reject as completed-return type mismatch; canonical-v3 COMPLETED requires `BacktestCanonicalPublicationRefV2` |

## Non-goals

- no second repository, resolver, registry, Reader/provider framework, proof DSL, or
  Builder import;
- no new Runtime facade, Local Reader root export, caller token, generic finalized
  result/outcome wrapper, `derive_v2` operation, or heuristic version dispatcher;
- no automatic recovery framework, PID/age stale-lock guessing, staging adoption,
  broad cleanup, or final-state auto-deletion;
- no Resolution policy change, provider qualification, Tushare/Binance qualification,
  A-share Profile/Build registration, or G12M receipt rewrite;
- no diverse implementation, trusted-root identity, remote/NFS/object-store durability,
  future-retention guarantee, copied-tree detection, or malicious-process guarantee;
- no change to accepted v1/v2 bytes, APIs, fixtures, directories, or behavior.

## Current planning-commit write set

This docs-only plan repair writes exactly:

- `docs/implementation/acceptance-matrix.md`;
- `docs/implementation/plans/README.md`;
- this parent plan; and
- the execution DAG plus DRP-00 through DRP-05 node plans under
  `docs/implementation/plans/g07-durable-rebuild-proof-v2/`.

## Authority map

| Fact | Sole authority |
| --- | --- |
| current Gate status | [Acceptance Matrix](../acceptance-matrix.md), unique `G07-DURABLE-REBUILD-PROOF-V2` row |
| current DRP node statuses, edges, WIP, Ready queue | [execution DAG](g07-durable-rebuild-proof-v2/README.md) |
| invariant meanings and exclusions | this parent plan |
| exact names, fields, preimages, failure codes, private seam, layouts | accepted DRP-00 research contract |
| node-local implementation and evidence | each DRP node plan |

Accepted historical `G07 PASSED` is unchanged and retains its development-run meaning.
DRP-00 has updated the new Matrix row to `READY` after H1. DRP-03 creates the immutable
Backtest code candidate; DRP-04 creates the separate Platform consumer-v2 commit
pinning that exact SHA; DRP-05 may update only that new Matrix row plus the DAG
README's DRP-04/DRP-05 projection after binding both commits. Platform may remain pinned to DRP-03 because DRP-05 is
docs/status only.
