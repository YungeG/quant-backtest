---
id: G12M-TUSHARE-PROSPECTIVE-CAUSAL-SUCCESSOR-V3
readiness: NOT_READY
status: DEFERRED_YAGNI_TARGETED_ROUTE_SEAM_UNDECIDED
owner: backtest-runtime / market-bundle-builder successor decomposition
predecessor: G12M-TUSHARE-FIXED-SINGLETON-QUALIFICATION-V2
latest_evidence: G12M-TUSHARE-JULY-LISTING-PRESENCE-BINDING-V2
---

# G12M Tushare prospective causal successor v3

## Outcome under investigation

A causal successor would move the zero-target decision after every accepted source
observation. The earliest frozen target is `1787543480633962556`, exactly one
nanosecond after the latest July listing observation. It would create a new target,
authority, execution Bundle, Run, and assessment while preserving all accepted v2
artifacts and claims.

## Evidence ordering

```text
G12I observed_at             1787292861381694496
G12K observed_at/floor       1787299622295499670
G12L 20240102 observed_at    1787533249650679470
G12L July observed_at        1787543480633962555
proposed target/floor        1787543480633962556
```

This ordering can support a prospective causal Run. The remaining question is whether
building another exact zero-target conformance route has enough value to justify the
route seam work.

## Diagnosis

Three additive seams exist without mutating accepted v2 modules:

1. A new authority can use accepted authority-v2 as predecessor, retain exact
   Market/Account/runtime components, and replace only the target commitment,
   target-dependent Simulation identity, and Build identity.
2. `G12MTushareFixedSingletonExecutionBundleResultV2` already exposes validated source
   Events, bar-open projections, lineage, catalog, manifest, and stream payloads. A v3
   Builder can consume the exact v2 result and replace only the target stream and
   resulting manifest/ref.
3. A new assessment can consume exact upstream reports and verified Run-v3 evidence,
   naming accepted assessment-v2 as its direct predecessor.

The unresolved seam is Runtime route orchestration. The accepted route-v2 module is
1091 lines and hardcodes decision time, target identity, request, Timeline, and route
result identity. Its helpers are private and its exact result class rejects changed
identities.

## Why implementation is deferred

Two honest route choices remain:

### R1 — focused additive route-v3

Create a new provider-specific route module, importing only stable domain/runtime
contracts and, where safe, exact private pure helpers from route-v2. It still needs a
new result class and orchestration for the new target/request/Run identities. This is
an additive fork of the route seam only, not of authority, Bundle projection, or
assessment logic.

### R2 — targeted route-core extraction

Extract only the target-independent orchestration from route-v2 into a private Runtime
core used by exact v2/v3 wrappers. Existing canonical v2 artifact/output hashes and
failure behavior must remain unchanged. Accepted route-v2 **source-file SHA sentinels**
would necessarily be retired/updated under explicit compatibility-refactor authority;
they cannot remain unchanged if the source file is edited.

Monkeypatching globals, dynamic constant overrides, caller mappings, or a cross-package
shared parameter object are rejected. Builder cannot import Runtime; each package owns
its own exact wrapper and cross-checks the canonical target event/digest at the artifact
boundary.

## Corrected vertical DAG

```text
P1 authority-v3 exact target commitment
  -> P2 Bundle-v3 exact target replacement
       -> P3 prospective route-v3
            -> P4 causal assessment-v3
P1 + P2 + P3 + P4 -> P5 governance fan-in
```

All edges are serial on the critical path. No speculative fan-out is authorized.

## P1 — additive authority v3

- **Outcome:** exact Profile/Build authority for target time
  `1787543480633962556` and a new target-stream digest.
- **Consumes:** accepted authority-v2 semantic identity and runtime component refs.
- **Produces:** authority-v3 canonical decision, registrations, Build manifest.
- **Exact write set:**
  - `packages/backtest-runtime/src/crypto_quant_backtest/cn_a_share_fixed_singleton_no_trade_profile_v3.py`
  - `tests/runtime/profiles/test_cn_a_share_fixed_singleton_no_trade_profile_v3.py`
  - `tests/architecture/test_cn_a_share_fixed_singleton_no_trade_profile_v3_boundary.py`
  - `tests/fixtures/runtime/cn-a-share-fixed-singleton-no-trade-profile-v3/`
- **Excludes:** Bundle, Run, assessment, grade changes, live/deployment.

## P2 — additive Bundle v3

- **Outcome:** consume the exact validated Bundle-v2 result, retain its 19 source Events,
  19 bar-open projections, lineage and catalog, replace only the target stream, then
  publish a new exact manifest/ref.
- **Consumes:** P1 target commitment and accepted Bundle-v2 result.
- **Produces:** Bundle-v3 result/fixture.
- **Exact write set:**
  - `packages/market-bundle-builder/src/crypto_quant_bundle_builder/g12m_tushare_fixed_singleton_execution_bundle_v3.py`
  - `tests/bundle_builder/providers/tushare/test_g12m_tushare_fixed_singleton_execution_bundle_v3.py`
  - `tests/architecture/test_g12m_tushare_fixed_singleton_builder_v3_boundary.py`
  - `tests/fixtures/market_data/providers/tushare/g12m-fixed-singleton-execution-bundle-v3/`
- **Excludes:** source/projection recomputation, provider I/O, Runtime import.

## P3 — prospective route v3

- **Outcome:** one sole-facade zero-target/no-trade Run whose target is after all
  accepted source observations.
- **Consumes:** P1 authority and P2 Bundle.
- **Produces:** exact route result, semantic Run, proof, Integrity, analysis.
- **Exact additive write set for R1:**
  - `packages/backtest-runtime/src/crypto_quant_backtest/g12m_tushare_fixed_singleton_route_v3.py`
  - `tests/runtime/g12m/test_tushare_fixed_singleton_route_v3.py`
  - `tests/architecture/test_g12m_tushare_fixed_singleton_route_v3_boundary.py`
  - `tests/fixtures/runtime/g12m-tushare-fixed-singleton-production-run-v3/`
- **Alternative R2 write conflict:** route-v2 module/tests/sentinels plus a new private
  route core; exact files require a separate Full implementation packet before edits.
- **Excludes:** direct Engine run, second facade, grade minting, live/deployment.

## P4 — causal assessment v3

- **Outcome:** exact source-to-Run assessment binding G12I/G12K, both G12L reports,
  July binding-v2, Bundle-v3, Run-v3, and copied Integrity grades.
- **Assessment floor:** `1787543480633962556`.
- **Predecessor policy:** direct predecessor is accepted assessment-v2
  `sha256:31f29b9ab70e7c8da267b6c17dcbe294503088850c894b066116313233dca8bb`.
- **Target evidence:** exact target event/digest/time must match P1/P2/P3; both G12L
  report hashes and the July direct-successor binding hash are mandatory.
- **Exact write set:**
  - `packages/backtest-runtime/src/crypto_quant_backtest/g12m_tushare_fixed_singleton_assessment_v3.py`
  - `tests/runtime/g12m/test_tushare_fixed_singleton_assessment_v3.py`
  - `tests/architecture/test_g12m_tushare_fixed_singleton_assessment_v3_boundary.py`
  - `tests/fixtures/runtime/g12m-tushare-fixed-singleton-assessment-v3/`
- **Claim ceiling:** evidence available before new target; completeness/finality,
  between-date listing continuity, legal/live/deployment remain unclaimed.

## P5 — governance fan-in

- **Outcome:** accepted or blocked receipt and status registry update.
- **Exact write set:**
  - `docs/implementation/acceptance-matrix.md`
  - `docs/implementation/plans/g12/README.md`
  - `docs/implementation/plans/g12/g12m-source-bounded-qualification-v1.md`
  - this plan
  - one versioned v3 acceptance or blocked receipt

## Dependency edges

| Edge | Type | Artifact crossing |
| --- | --- | --- |
| accepted v2 authority -> P1 | contract | predecessor authority/components |
| P1 -> P2 | contract | exact target event/digest and authority-v3 |
| accepted Bundle-v2 -> P2 | evidence | validated source/projection result |
| P2 -> P3 | evidence | Bundle-v3 manifest/ref/membership |
| P3 -> P4 | evidence | verified Run-v3/Integrity/proof/analysis |
| accepted G12I/G12K/G12L/bindings -> P4 | evidence | canonical reports/times/hashes |
| P1..P4 -> P5 | evidence + write conflict | accepted commits/hashes |

The graph is acyclic and serial. One writer is active at a time.

## Proof budget

- P1: focused authority/profile/Build exact-identity tests.
- P2: focused Bundle-v2 reuse, target replacement, publication and architecture tests.
- P3: facade/PREP/Resolution/Integrity/repository/analysis adjacent tests plus full
  repository because it creates the new Run seam.
- P4: adversarial canonical/time/grade/predecessor tests.
- P5: mandatory final full-repository run because P4 changes code after P3, import
  boundaries, LSP/lens, gitleaks, artifact hashes, independent final review, protected
  dirty bytes, and no push without approval.

## Readiness decision

**NOT_READY / DEFERRED_YAGNI.** Additive authority, Bundle, and assessment designs are
available. The targeted route seam (R1 additive route versus R2 compatibility
extraction) is undecided, and a prospective zero-target duplicate Run currently has no
caller-visible research value.

Default recommendation: stop. Reopen only when either:

1. a concrete nonzero prospective strategy/use case needs causal qualification; or
2. the user explicitly chooses R1 or authorizes the R2 compatibility refactor.
