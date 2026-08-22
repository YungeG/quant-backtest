---
id: G12M-TUSHARE-FIXED-SINGLETON-QUALIFICATION-V1-EXECUTION
status: RESEARCH_GATE_REQUIRED
owner: Tushare fixed-singleton qualification consuming independent authority
source_plan: ../g12m-tushare-fixed-singleton-qualification-v1.md
status_authority: ../../../acceptance-matrix.md
---

# G12M Tushare fixed-singleton execution DAG

## Outcome

Execute the [parent contract](../g12m-tushare-fixed-singleton-qualification-v1.md)
without allowing G12M, its assessor, or accepted provider evidence to bootstrap a
production Profile, Build, resolved environment, Integrity grade, or assessment.

## Current Ready state

- **Completed by this docs contract:** [BHA-00](bha-00-contract-freeze.md).
- **Ready now:**
  [BHA-01](bha-01-profile-resolution-build-authority-gate.md), independently owned
  prerequisite-identity research only.
- **Code Ready:** none. Current evidence does not satisfy BHA-01 H1.
- **Current blockers:** the current China A-share Profile and selected rule/fee
  bindings are DEVELOPMENT-only; no independently accepted exact applicable
  component/Profile/Build authority exists; accepted G12I supplies neither the
  schema-3 `price_bars@1` observation capability nor the current development
  simulation's `bar_open@1`; no causal complete execution Bundle exists; and current
  HEAD lacks a separately and independently accepted generic durable rebuild/retention
  proof seam. Integrity checks only non-null proof-hash presence, so a facade-generated
  opaque hash cannot be acceptance evidence. The missing proof seam is an exact
  controllable H2 condition independent of any missing applicable Profile/Build
  authority.
- **Strict-closure disposition:** missing strict G12H successor, official, or legal
  closure alone is an ADR-0008 limitation/nonclaim, not H2, unless an exact selected
  production component makes that controllable fact applicable.

## DAG

```text
BHA-00 CONTRACT_COMPLETE ──────────────────────────────────┐
independently accepted applicable Profile/Build authority ─┤
independently accepted generic durable proof prerequisite ─┤
                                                           ▼
BHA-01 INDEPENDENT_RESEARCH_READY
   ├─ H2 ─× BHA-02, BHA-03, BHA-04 TERMINATED_H2
   │          │ blocked decision
   │          └──────────────────────────────→ BHA-05 H2 governance fan-in
   └─ H1 (only after both prerequisites are accepted)
       ├─ authority evidence ───────────────────────────────→ BHA-04
       │ immutable prerequisite identities                      ▲
       ▼                                                         │
BHA-02 Builder projection/execution Bundle ──────────────────────┤
       │ contract + evidence                 ╲ direct Bundle hashes
       ▼                                      ╲
BHA-03 Profile registration + Resolution + facade/PREP/Runner/Integrity Run
       │ canonical Run evidence                ╲ direct Run/proof-body/repository hashes
       ▼                                        ▼
BHA-04 pure Runtime schema-2 assessment ─────→ BHA-05 H1 success governance fan-in
```

The graph is acyclic. BHA-01 only binds immutable identities of separately accepted
applicable Profile/Build authority and generic durable proof prerequisites. It does
not design or implement either prerequisite. BHA-02 owns Bundle/projection
construction; existing Runtime Resolution owns compatibility and the resolved
environment; the independently accepted generic seam verifies/recomputes proof before
Integrity and repository replay verifies the same body/hash; existing Integrity alone
owns grade; BHA-04 only binds already-decided outcomes. H2 bypasses all code nodes and
enters BHA-05 directly.

## Nodes

| ID | Ready state | Produces | Contract dependencies | Evidence dependencies | Write conflicts |
| --- | --- | --- | --- | --- | --- |
| [BHA-00](bha-00-contract-freeze.md) | CONTRACT_COMPLETE | accepted exact contract, protected-history baseline, and current status-authority reconciliation | parent plan, ADR 0008 | current HEAD seam findings | plan tree + minimal Acceptance Matrix/G12 README status |
| [BHA-01](bha-01-profile-resolution-build-authority-gate.md) | INDEPENDENT_RESEARCH_READY | immutable H1 binding both accepted prerequisite identities, or H2 | BHA-00 case boundary, ADR 0008 | independently accepted applicable Profile/Build authority plus independently accepted generic durable proof prerequisite | independent decision artifacts |
| [BHA-02](bha-02-builder-execution-bundle.md) | BLOCKED_H1 | minimum causal projections, one complete published execution Bundle, and exact G12D retention-proof identity | BHA-01 H1, G12C/D | exact G12I Events and accepted catalog | Builder provider module/fixture |
| [BHA-03](bha-03-production-profile-run.md) | BLOCKED_BHA02 | exact Profile registrations, Resolution outcome, production-path consumption of the accepted proof implementation, facade/PREP Run, Integrity/canonical publication, and off-root verified-run repository view | BHA-01 H1, BHA-02 | immutable Build inputs, exact Bundle, accepted generic proof prerequisite | provider Profile/run/repository-view files only |
| [BHA-04](bha-04-runtime-assessment.md) | BLOCKED_RUN | pure additive schema-2 initial source-to-Run assessment and fail-closed successor contract | BHA-01 H1, BHA-02, BHA-03 | exact independently accepted authority decision, exact G12I/G12K bytes, and provider-specific verified-run evidence | provider-specific Runtime assessor v2 |
| [BHA-05](bha-05-governance-fanin.md) | BLOCKED_ROUTE | H1-success acceptance receipt or H2-blocked/terminated receipt and registry status | BHA-01 route; BHA-02/BHA-03/BHA-04 directly on H1 | route-specific immutable tips and protected fingerprints | Acceptance Matrix/G12 README/main branch |

## Typed edges

| From | To | Type | Consumed artifact |
| --- | --- | --- | --- |
| BHA-00 | BHA-01 | contract | fixed case boundary, stop rules, protected bytes |
| accepted Profile/Build prerequisite | BHA-01 H1 | authority prerequisite | exact selected component/Profile required-capability, immutable Build, and source-binding facts |
| accepted generic proof prerequisite | BHA-01 H1 | proof prerequisite | immutable accepted identity for durable canonical proof body/schema, independent pre-Integrity verification/recomputation, repository replay, and v1 preservation |
| BHA-01 H1 | BHA-02 | authority evidence | exact selected component/Profile required-capability and source-binding facts |
| BHA-01 H1 | BHA-03 | authority evidence | exact Profile-registration and immutable Build inputs plus accepted proof-prerequisite identity |
| BHA-01 H1 | BHA-04 | authority evidence | exact independently accepted initial decision binding both prerequisite identities and accepted G12I/G12K identities; future source changes require its accepted direct successor |
| BHA-02 | BHA-03 | contract + evidence | exact execution Bundle ref/manifest/events and publication proof |
| BHA-02 | BHA-04 | evidence | exact Bundle membership and projection lineage |
| BHA-02 | BHA-05 | H1 Bundle/proof evidence | direct Bundle/projection/report/publication and G12D retention-proof hashes consumed by governance |
| BHA-03 | BHA-04 | evidence | Resolution outcome and repository-verified canonical Run, trace, grade, publication identities |
| BHA-03 | BHA-05 | H1 Run/proof evidence | direct Profile/Build/Resolution/Run, accepted canonical proof-body/hash identity, Integrity/publication/repository and verified-run hashes consumed by governance |
| BHA-04 | BHA-05 | H1 acceptance evidence | accepted schema-2 assessment bytes/hash and predecessor disposition |
| BHA-01 H1 | BHA-05 | H1 authority evidence | immutable independently accepted authority decision and manifest |
| BHA-01 H2 | BHA-02..04 | termination | explicit missing/unaccepted applicable Profile/Build authority or generic durable proof prerequisite; no placeholder output |
| BHA-01 H2 | BHA-05 | blocked governance | immutable H2 decision and terminated-node disposition |

No write-conflict edge substitutes for a missing contract or evidence edge.

## Exact write-set ownership

| Node | Exact future write set |
| --- | --- |
| BHA-00 | this plan tree; link/status-only edits to `../g12m-source-bounded-qualification-v1.md` and `../README.md`; minimal current-status edit to `docs/implementation/acceptance-matrix.md` |
| BHA-01 | `docs/research/g12m-tushare-fixed-singleton-prerequisite-authority-v1.md`; `evidence/g12m-tushare-fixed-singleton-prerequisite-authority-v1/decision.json`; `evidence/g12m-tushare-fixed-singleton-prerequisite-authority-v1/manifest.sha256` |
| BHA-02 | `packages/market-bundle-builder/src/crypto_quant_bundle_builder/g12m_tushare_fixed_singleton_execution_bundle_v1.py`; `tests/bundle_builder/providers/tushare/test_g12m_tushare_fixed_singleton_execution_bundle_v1.py`; `tests/architecture/test_g12m_tushare_fixed_singleton_builder_boundary.py`; `tests/fixtures/market_data/providers/tushare/g12m-fixed-singleton-execution-bundle-v1/` |
| BHA-03 | `packages/backtest-runtime/src/crypto_quant_backtest/g12m_tushare_fixed_singleton_profile_v1.py`; `packages/backtest-runtime/src/crypto_quant_backtest/evidence_repository.py`; `packages/backtest-runtime/src/crypto_quant_backtest/g12m_tushare_fixed_singleton_verified_run_v2.py`; `tests/runtime/g12m/test_tushare_fixed_singleton_production_run_v1.py`; `tests/runtime/evidence_repository/test_g12m_tushare_fixed_singleton_verified_run_v2.py`; `tests/runtime/analysis/test_analysis_derivation_boundary.py`; `tests/architecture/test_g12m_tushare_fixed_singleton_runtime_boundary.py`; `tests/fixtures/runtime/g12m-tushare-fixed-singleton-production-run-v1/` |
| BHA-04 | `packages/backtest-runtime/src/crypto_quant_backtest/g12m_tushare_fixed_singleton_assessment_v2.py`; `tests/runtime/g12m/test_tushare_fixed_singleton_assessment_v2.py`; `tests/architecture/test_g12m_tushare_fixed_singleton_assessment_boundary.py`; `tests/fixtures/runtime/g12m-tushare-fixed-singleton-assessment-v2/` |
| BHA-05 | `docs/implementation/acceptance-matrix.md`; `../README.md`; `../g12m-source-bounded-qualification-v1.md`; `bha-02-builder-execution-bundle.md`; `bha-03-production-profile-run.md`; `bha-04-runtime-assessment.md`; this `README.md`; exactly one of `bha-05-h1-acceptance-receipt.md` or `bha-05-h2-blocked-receipt.md` |

A node may delete an unnecessary planned file after call-site tracing, but it may not
write outside its row without a new contract decision. In particular, no node edits accepted G12I/G12K/Binance modules or fixtures. BHA-01
writes no G12M assessor, Profile registration, proof implementation, Resolution/
Integrity implementation, Bundle, Run, or registry. BHA-03 writes no `facade.py`,
`integrity.py`, `local_market_bundle_reader.py`, or proof generation.

## WIP policy

- One active writer in the working tree.
- Before H1/H2: at most BHA-00 plus one independent BHA-01 research task; zero code
  writers.
- After H1: one code node active at a time. BHA-02 completes before BHA-03 because the
  exact Bundle is a ProfileResolver/Run input.
- After H2: BHA-02 through BHA-04 are terminated; only BHA-05 governance may write
  their status fields, this DAG status, registries, and the one H2 route receipt.
- Read-only review may run in parallel; registry/main-branch fan-in remains BHA-05
  single-writer work.
- No speculative BHA-02/BHA-03 skeleton, placeholder authority, test-only production
  Profile, or synthetic successful assessment may be committed while BHA-01 is open.

## Failure precedence

1. BHA-01 H2 for either missing independently accepted applicable Profile/Build
   authority or missing independently accepted generic durable proof prerequisite
   terminates BHA-02 through BHA-04 and routes to BHA-05; BHA-05 validation failure
   then owns the blocked-route status.
2. On H1, BHA-02 cannot publish an exact causal complete Bundle.
3. BHA-03 Resolution cannot resolve compatible Profile/Build/Bundle/Environment, the
   already accepted generic proof implementation is not consumed through the existing
   production path, its independent pre-Integrity verification fails, repository
   replay of the same canonical proof body/hash fails, or the production path cannot
   publish a decision-grade Run through Integrity.
4. BHA-04 cannot reconstruct and bind source, Run, trace, grade, Bundle, accounting,
   time, and predecessor identities.
5. BHA-05 detects protected-byte, registry, link, validation, or secret failure on
   either route.

The first applicable failure owns the status. A later node never downgrades, masks,
or repairs it.

## Proof budget

| Risk | Nodes | Required proof |
| --- | --- | --- |
| High — authority/bootstrap | 01, 03 | both prerequisite identities independently accepted, no proof/G12M-to-Profile/Build/grade edge, Resolution outcome, unchanged Integrity grade policy |
| High — provider identity/time/correction | 01, 02, 04 | exact canonical reconstruction, `(event_id,event_hash,timeline_instant)` lineage, strict pre-decision causal cut, initial-authority binding, and fail-closed unaccepted/G12I-only successor tests |
| High — accounting | 01, 03, 04 | zero exposure/no-entitlement/no-dispatch invariants and explicit nonclaims |
| Medium — one-Bundle Runtime composition | 02, 03 | G12C/D publication, schema-3 replay, resolver compatibility, no cross-Bundle read/fallback |
| High — production proof origin | prerequisite, 01, 03 | separately accepted durable canonical proof body and exact schema; independent pre-Integrity verification/recomputation against immutable execution evidence; production-path consumption only; repository replay of the same body/hash; no facade self-attestation; v1 parity |
| Medium — shared repository view | 03 | exact `VerifiedCompletedPublicationV2` API/bytes frozen; off-root provider evidence from one private verification path; focused tamper/boundary tests |
| Low — governance links/status | 00, 05 | H1/H2 route coverage, Markdown/link/diff/secret checks and protected fingerprints |

Validation pyramid:

```text
BHA-01 decision   canonical decision + independent Profile/Build and accepted-proof-prerequisite review
BHA-02            focused Builder/G12C/D + architecture
BHA-03            focused facade/PREP/Resolution/Runner/Integrity/repository + full suite
BHA-04            focused additive schema-2 assessment adversarial + adjacent Runtime + full suite at acceptance
BHA-05            route receipt, immutable hashes, links, diff, gitleaks, registry consistency
```

## Ready queue

| Priority | Node | Current state | Unblocks |
| --- | --- | --- | --- |
| 1 | BHA-00 | CONTRACT_COMPLETE | BHA-01 |
| 2 | BHA-01 | INDEPENDENT_RESEARCH_READY | H1 starts BHA-02; H2 starts only BHA-05 |
| 3 | BHA-02 | NOT_READY | BHA-03/BHA-04 on H1 |
| 4 | BHA-03 | NOT_READY | BHA-04 on H1 |
| 5 | BHA-04 | NOT_READY | BHA-05 success route |
| 6 | BHA-05 | NOT_READY | final success or blocked registry receipt |

## Fan-in acceptance

BHA-05 has exactly two legal inputs:

- **H1 success:** immutable accepted BHA-01 H1 binding both independent prerequisite
  identities plus direct typed BHA-02 Bundle, BHA-03 Run/accepted-proof/repository,
  and BHA-04 schema-2 assessment evidence. It sets
  BHA-02/BHA-03/BHA-04 to `ACCEPTED_H1`, this DAG to `ACCEPTED_H1`, writes
  `bha-05-h1-acceptance-receipt.md`, and must not create the H2 receipt.
- **H2 blocked:** immutable accepted BHA-01 H2 only. It verifies BHA-02 through BHA-04
  produced no output, sets each to `TERMINATED_H2`, this DAG to `BLOCKED_H2`, writes
  `bha-05-h2-blocked-receipt.md`, and must not create the H1 receipt.

Both routes must verify protected G12I/G12K/Binance bytes, links, graph/status
consistency, diff, and gitleaks. H2 must not imply a Profile registration, Bundle,
Run, Integrity result, or assessment exists. BHA-00 has already reconciled the
Acceptance Matrix to the current research-gate/code-not-ready state; BHA-05 alone
later writes the final H1-success or H2-blocked route status.
