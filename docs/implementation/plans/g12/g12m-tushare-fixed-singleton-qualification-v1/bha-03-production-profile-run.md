---
id: G12M-TFS-BHA-03
status: BLOCKED_BHA02
owner: Runtime provider Profile/run/repository-view single writer
produces:
  - exact Profile registrations implementing immutable BHA-01 authority
  - one ProfileResolver-resolved facade/PREP/Runner/Integrity canonical-v2 Run
  - provider-specific exact verified-run repository view without changing the public completed view
consumes:
  - G12M-TFS-BHA-01 H1 binding both independently accepted prerequisites
  - G12M-TFS-BHA-02 execution Bundle
  - already accepted generic durable rebuild/retention proof implementation through the existing production path
depends_on:
  contract: [G12M-TFS-BHA-01-H1, G12M-TFS-BHA-02, PREP-COVERAGE-01]
  evidence: [independently authorized immutable Build inputs, exact execution Bundle, immutable accepted generic proof-prerequisite identity]
  write_conflict: [runtime-profile-registration, runtime-provider-verified-run-evidence]
fan_in: [G12M-TFS-BHA-04, G12M-TFS-BHA-05]
---

# BHA-03 Establish grade through the production Runtime path

## Outcome

On hypothetical BHA-01 H1, implement only the exact additive provider Profile
registrations authorized by the independently accepted Profile/Build prerequisite;
present those registrations, the immutable Build, and the BHA-02 Bundle to existing
`ProfileResolver`; consume the already accepted generic durable rebuild/retention
proof implementation through the existing production path; and generate the first
accepted canonical-v2 Run through the real facade/PREP/Runner/Integrity/publication
path.

BHA-03 does not design, implement, generate, or self-attest proof. It does not write
`facade.py`, `integrity.py`, or `local_market_bundle_reader.py`. A facade-generated
opaque hash, including one made after two reconstructions by the same implementation,
is insufficient because current Integrity checks only non-null proof-hash presence.

`ProfileResolver` alone decides runtime Bundle/Build/Profile/Environment compatibility.
The independently accepted generic seam must complete its independent pre-Integrity
verification/recomputation. Integrity alone must return requested and result grade as
`DECISION_GRADE`. If any authority rejects its inputs, this node fails; G12M cannot
repair or reinterpret the outcome.

## Profile invariants

- use existing registration, registry, and `ProfileResolver` types;
- additive exact keys/versions; do not flip or relabel existing DEVELOPMENT
  `CnAShareResolvedProfile` registrations;
- exactly implement BHA-01 component/Profile authority and exact G12I/G12K source
  bindings without deriving eligibility from provider acceptance;
- exact fixed singleton and no dynamic selector;
- exact accepted H1 required capabilities, no fallback to development/current
  registration;
- no G12M contract, assessor input, assessor output, or proof value in Profile/Build
  eligibility; and
- corrections change the Profile semantic identity and thus semantic Run ID.

## Production journey invariants

- invoke `BacktestRuntime.run()` with schema-3 execution inputs;
- use one retained Reader for exactly the BHA-02 Bundle;
- PREP v3 replays embedded bindings against that Reader;
- `ProfileResolver` receives the independently authorized immutable Build and exact
  Profile registrations and remains sole runtime compatibility/eligibility authority;
- the already accepted generic proof implementation is consumed only through its
  existing production path and independently verifies/recomputes its exact versioned
  durable canonical proof body against immutable execution-input, Bundle, PREP,
  Resolution, execution-case, attempt, and attempt-evidence inputs before Integrity;
- `AuditableBacktestRunner.for_v2()` executes its existing deterministic-attempt
  contract; BHA-03 does not substitute a provider proof generator;
- exact zero-target semantics produce zero orders, fills, fees, settlement
  obligations, lots, position exposure, and corporate-action dispatches;
- the execution trace contains exactly one entry for every accepted G12I
  `(event_id, event_hash, timeline_instant)` triple; the frozen zero-target decision
  UTC time is strictly after the latest source `available_time`, its
  `SimulationInstant` is strictly after every source `timeline_instant`, every
  represented source phase is prior, and no accepted source is consumed post-decision;
- `IntegrityEvaluator` is unchanged grade authority;
- `CanonicalResultPublisher` publishes canonical-v2 atomically; and
- `BacktestEvidenceRepository` replays the same accepted canonical proof body/hash and
  verifies the publication through its existing completed-publication path.

No direct Engine-only journey, manually created finalized Result, copied golden
publication, synthetic Integrity report, caller proof, naked hash, or test-only
decision-grade Profile is accepted.

## Accepted generic proof prerequisite consumption

BHA-01 H1 can exist only after the generic proof prerequisite is separately and
independently accepted. BHA-03 treats its immutable acceptance identity as an input,
not an implementation request. The accepted prerequisite must already guarantee:

- a durable canonical proof body, not only a non-null hash;
- one exact versioned schema;
- verification/recomputation by an independent pre-Integrity path against immutable
  execution-input, Bundle, PREP, Resolution, case, attempt, and attempt-evidence data;
- repository replay of the same canonical body and hash; and
- preservation of all existing v1 APIs and bytes.

This plan intentionally does not name a new generic G07 gate, schema type, module,
algorithm, or write set. Those belong to a separately proposed and independently
accepted prerequisite, not to G12M or this provider lane.

## Existing repository reuse without public-view mutation

`VerifiedCompletedPublicationV2` is an exact exported public API. Preserve its exact
constructor parameter order, fields, `from_finalized` behavior, root export, bytes,
and all existing consumers. Do not add proof or assessment fields to it.

BHA-03 may add one off-root provider-specific exact verified-run evidence value. Build
it only through a private reuse/refactor of the existing `BacktestEvidenceRepository`
completed-publication verification path: the shared private path verifies the same
root/children, source hashes, canonical identities, attempts, accepted proof body/hash,
Result, Integrity context/report, engine context, full trace, Bundle identities, and
execution summary once; `load_completed(ref)` projects the unchanged
`VerifiedCompletedPublicationV2`, while the private provider-specific entry point
projects the richer exact value needed by BHA-04.

No second repository, duplicated parser/graph walk, provider file loader, proof
verifier, public repository method, `load_completed` signature/behavior change, or
root export is allowed.

## Exact write set

- `packages/backtest-runtime/src/crypto_quant_backtest/g12m_tushare_fixed_singleton_profile_v1.py`
- `packages/backtest-runtime/src/crypto_quant_backtest/evidence_repository.py`
- `packages/backtest-runtime/src/crypto_quant_backtest/g12m_tushare_fixed_singleton_verified_run_v2.py`
- `tests/runtime/g12m/test_tushare_fixed_singleton_production_run_v1.py`
- `tests/runtime/evidence_repository/test_g12m_tushare_fixed_singleton_verified_run_v2.py`
- `tests/runtime/analysis/test_analysis_derivation_boundary.py`
- `tests/architecture/test_g12m_tushare_fixed_singleton_runtime_boundary.py`
- `tests/fixtures/runtime/g12m-tushare-fixed-singleton-production-run-v1/`

No `facade.py`, `integrity.py`, `local_market_bundle_reader.py`,
`verified_publications.py`, `runner.py`, `resolution.py`, PREP implementation,
proof generation/verification implementation, Builder, G12D repository, Kernel,
Runtime/Market Data root export, accepted fixture, Acceptance Matrix, or G12 README
edit. Shared-file change is limited to the provider-specific repository view while
preserving the existing completed-publication path and public view.

## Failure precedence

1. malformed/unaccepted BHA-01 or BHA-02 identity;
2. accepted generic proof-prerequisite identity is missing or mismatched;
3. Profile/component source binding mismatch;
4. immutable Build authority/input mismatch;
5. resolver Profile/Build/Bundle/Environment incompatibility or ineligibility;
6. PREP retained-Reader or replay mismatch;
7. singleton/zero-target semantic mismatch;
8. Runner/attempt/evidence publication failure;
9. execution trace or accounting disposition mismatch;
10. independent pre-Integrity proof verification/recomputation or canonical proof-body
    identity mismatch;
11. Integrity requested/result grade mismatch or blocking issue;
12. canonical publication failure;
13. repository replay of the same proof body/hash or provider verified-run projection
    mismatch; or
14. deterministic repeat/correction identity mismatch.

## Acceptance

- existing DEVELOPMENT Profile bytes/behavior remain unchanged;
- exact production Profile cannot be reconstructed from development authority or any
  G12M/assessor/proof output;
- real facade returns a canonical publication ref, not a synthetic object;
- the already accepted proof implementation independently verifies/recomputes its
  durable canonical body before Integrity and the repository replays the same body/hash;
- no facade-generated opaque hash, same-implementation double reconstruction, caller
  hash, mapping, duck value, or provider code can bootstrap Integrity;
- all 19 accepted G12I `(event_id, event_hash, timeline_instant)` triples occur
  exactly once in `TIMELINE_EVENT` trace; the decision UTC time and
  `SimulationInstant` are strictly later, every represented source phase is prior,
  and post-decision source consumption fails;
- zero-exposure accounting disposition and nonclaims hold;
- Integrity requested/result grade are exact decision grade and deployment remains
  false, with no policy change or proof-to-grade bootstrap;
- unchanged `VerifiedCompletedPublicationV2` and the off-root exact verified-run view
  are both projected from the same repository verification path;
- initial acceptance covers the initial source identities and proves fail-closed
  rejection of G12I-only correction, unaccepted G12K successor, or any source change
  lacking a new independently accepted BHA-01 direct-successor decision; and
- focused facade/PREP/resolver/Runner/Integrity/repository, architecture, full suite,
  Ruff/Pyright, diff, gitleaks, and independent grade/accounting reviews pass.
