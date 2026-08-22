---
id: G12M-TUSHARE-FIXED-SINGLETON-QUALIFICATION-V1
readiness: RESEARCH_GATE_REQUIRED
status_authority: ../../acceptance-matrix.md
owner: Runtime source-bounded qualification consuming independent Profile/Resolution/Build and durable-proof authority
produces:
  - exact Tushare fixed-singleton G12M contract
  - one production-path canonical Run and read-only assessment, only after the independent gate passes
  - H1-success or H2-blocked governance fan-in
consumes:
  - ADR 0008
  - accepted G12I Tushare daily source-bounded v2 report
  - accepted G12K Tushare fixed-instrument source-bounded v1 report
  - existing PREP v3, ProfileResolver, BacktestRuntime, AuditableBacktestRunner, Integrity, canonical publication, and BacktestEvidenceRepository
  - existing G12C/G12D MarketBundle validation and publication
  - accepted Binance H3 governance state as protected unrelated history
depends_on:
  contract: [G07, PREP-COVERAGE-01, G12C, G12D, G12I-TUSHARE-CN-A-SHARE-DAILY-SOURCE-BOUNDED-V2, G12K-TUSHARE-FIXED-INSTRUMENT-SOURCE-BOUNDED-V1, G12M-SOURCE-BOUNDED-QUALIFICATION-V1]
  evidence:
    - exact accepted G12I and G12K canonical bytes and hashes
    - immutable independently accepted applicable Profile/Build authority not yet available
    - separately and independently accepted generic durable rebuild/retention proof prerequisite not yet available
  write_conflict: [runtime-profile-registration, runtime-provider-verified-run-evidence, acceptance-registry]
execution_dag: g12m-tushare-fixed-singleton-qualification-v1/README.md
---

# G12M Tushare fixed-singleton qualification v1

## Outcome

Qualify one exact, no-dynamic-selector Tushare case for
`InstrumentId(VenueId("xshe"), "000001")` without widening G12I/G12K claims,
constructing grade in G12M, or bypassing the production execution path.

The first accepted success, if the authority gate passes, must be produced by:

```text
BacktestRuntime facade
  → schema-3 execution-input read/decode → retained Bundle replay → PREP replay
  → existing ProfileResolver → target/spec/manifest/case composition
  → separately accepted generic durable rebuild/retention proof implementation,
      through its existing production path, independently verifies/recomputes the
      canonical proof body before Integrity
  → AuditableBacktestRunner
  → existing IntegrityEvaluator
  → existing CanonicalResultPublisher
  → existing BacktestEvidenceRepository replays the same proof body/hash
  → pure provider-specific G12M assessment
```

A manually constructed `ResolvedExecutionCase`, fabricated finalized publication,
synthetic completed Result, test-only decision-grade Profile, or direct assessor-created
grade is not acceptance authority.

## Current decision: no code lane is Ready

**Current evidence does not support starting implementation after the contract node.**
The accepted G12I and G12K reports close the provider-evidence inputs for this fixed
source scope, but they do not close independent production
Profile/Resolution/Build authority, the generic durable rebuild/retention proof
prerequisite, or the causal Runtime market-data shape.

The immediate route is the independently owned prerequisite gate in
[BHA-01](g12m-tushare-fixed-singleton-qualification-v1/bha-01-profile-resolution-build-authority-gate.md).
BHA-02 through BHA-04 remain blocked unless BHA-01 reaches its exact accepted `H1`
outcome after both independent prerequisites are accepted. An `H2` outcome terminates
only those code nodes and routes directly to BHA-05 for the sole blocked governance
receipt/registry update; it creates no code, Run, assessment, or grade.

Concrete blockers at current HEAD:

1. [`CnAShareResolvedProfile`](../../../../packages/backtest-runtime/src/crypto_quant_backtest/cn_a_share_profile.py)
   exact-reconstructs DEVELOPMENT registrations with
   `decision_grade_eligible=false`; the current-selected fee binding is likewise a
   development projection. Those artifacts cannot self-authorize H1 and G12M cannot
   relabel them.
2. [`ProfileResolver`](../../../../packages/backtest-runtime/src/crypto_quant_backtest/resolution.py)
   rejects a decision-grade request unless the exact Profile registrations and Build
   presented at runtime are eligible and compatible. Existing
   [`IntegrityEvaluator`](../../../../packages/backtest-runtime/src/crypto_quant_backtest/integrity.py)
   independently preserves the same boundary and remains sole result-grade authority.
3. Accepted G12I publishes only
   `tushare_cn_a_share.daily-publications@1`. The current schema-3 multi-resolution
   preparation path requires `price_bars@1` for each declared observation binding,
   while the current DEVELOPMENT China A-share simulation Profile declares
   `bar_open@1`. The accepted G12I report explicitly provides neither generic
   capability.
4. If the independently selected production simulation component still uses
   [`BarOpenObservation`](../../../../packages/backtest-runtime/src/crypto_quant_backtest/execution.py),
   it requires `event_time == available_time`; accepted G12I daily Events have July
   event times and late August acquisition availability, so they cannot be relabeled
   as causal bar-open Events. BHA-02 must use only a contract honestly supported by
   the accepted H1 components and current Runtime seams.
5. Accepted G12I Bundle coverage ends at the July target boundary, but the 19 Events
   become available in August. Any execution Bundle and Timeline window claiming to
   consume them must permit their exact Runtime availability; assessment time cannot
   substitute for Timeline visibility.
6. No independently accepted production Profile/component/Build authority exists for
   this exact case. Missing strict G12H successor, official, or legal closure alone is
   not a source-bounded blocker under ADR 0008; it remains a limitation/nonclaim unless
   an exact selected production component has a controllable contract that genuinely
   requires it.
7. Current HEAD has no separately and independently accepted generic decision-grade
   rebuild/retention proof seam. Integrity currently checks only whether the two proof
   hash fields are non-null; it does not verify a durable proof body. Therefore a
   facade-generated opaque hash—even after two reconstructions by the same
   implementation—could clear those presence checks and is not acceptance evidence.
   The missing accepted proof seam is an exact controllable H2 condition independent
   of any missing applicable Profile/component/Build authority.

These are independent authority, compatibility, proof, and causality boundaries, not
requests for G12M to invent a Profile grade, Build eligibility, generic G07 proof
implementation, resampler, or availability rule.

## Frozen source bounds

### G12I is provider evidence only

Accepted G12I canonical bytes are type
`tushare_cn_a_share_daily_source_bounded_observation_report`, schema version `2`.
They bind:

- provider `tushare.pro` and datasets `daily`, `trade_cal`, `suspend_d`;
- exact fixed instrument `xshe:000001` and July-2026 source scope;
- exactly one capability, `tushare_cn_a_share.daily-publications@1`;
- exactly one stream,
  `tushare_cn_a_share.daily.publication.xshe.000001.v1`;
- exactly 19 ordered Event hashes;
- report `sha256:ff09c4ad9f8025e66689387b5132d3d85c4101276fbf7330dd5040af111cc029`;
- canonical file `sha256:9cbfc115e41f56d1e83eac520856c3f529f83972b97111238e5dbb1a68c4eae6`;
- observed-at `1787292861381694496` epoch nanoseconds; and
- all qualification, grade, listing, corporate-action, provider, live, and
  deployment flags false.

The accepted G12I Bundle is evidence membership, not a complete production execution
Bundle. Its execution-reference and valuation requirements are exact-bucket,
zero-age, and no-forward-fill, but they do not satisfy current Runtime
`price_bars@1` or `bar_open@1` contracts by themselves.

### G12K is fixed observed-as-of evidence only

Accepted G12K canonical bytes are type
`g12k_fixed_instrument_source_bounded_observation_report`, schema version `1`.
They bind:

- exactly `xshe:000001`, with no dynamic selector or instrument substitution;
- one full `dividend(ts_code="000001.SZ")` response;
- 96 ordered retained source rows;
- zero rows selected by the exact target-date relevance predicate;
- report `sha256:5a49065d87286a9673893337328ddbbab9a19cd3addf178bf96033b9b1babfd7`;
- canonical file `sha256:a386f4281374d1449c0b5ba4371b9e9d2de5b236bc8fc5b5cdd8de5e43c65956`;
- observed-at `1787299622295499670` epoch nanoseconds; and
- all closure, authority, listing, continuity, universe, survivorship, lifecycle,
  grade, Profile, live, and deployment flags false.

Zero selected rows means only
`NO_TARGET_RELEVANT_ROW_RETURNED_AT_OBSERVED_AS_OF`. It is not listing authority,
listing continuity, survivorship safety, corporate-action absence, lifecycle
closure, provider completeness, correction closure, or finality.

## Grade firewall and authority order

The authority order is exact:

```text
accepted G12I/G12K provider evidence
  + independently accepted applicable component/Profile/Build authority
  + separately and independently accepted generic durable rebuild/retention proof seam
      → BHA-01 binds both immutable prerequisite identities as H1
      → exact Profile registrations and immutable Build inputs
      → existing ProfileResolver decides Bundle/Build/Profile/Environment compatibility
      → production facade/PREP/Runner consumes the accepted proof implementation
      → independent pre-Integrity proof verification/recomputation
      → existing Integrity alone decides requested/result grade
      → canonical publication and repository replay of the same proof body/hash
      → G12M read-only assessment copies and binds those outcomes
```

Forbidden cycles:

```text
G12M assessment → Profile eligibility
G12M assessment → Build eligibility
G12M assessment → requested ResultGrade
G12M assessment → Integrity result grade
successful assessment → authority for its own Run or Bundle
```

The independent BHA-01 lane requires exact G12I/G12K report identities in the Profile
semantic identity so a correction creates a new semantic Run, but those provider
reports cannot by themselves set `decision_grade_eligible=true`. H1 exists only after
independent acceptance of both the exact applicable component/Profile/Build authority
and the generic durable proof prerequisite. BHA-01 consumes and binds their immutable
identities; it does not design, implement, recompute, or self-attest either one.
`ProfileResolver` still decides runtime eligibility and compatibility, and Integrity
alone decides grade. Strict closure unknown remains a limitation/nonclaim unless an
exact selected production component makes that controllable fact applicable.

## Exact singleton execution case

The narrow accepted target, if BHA-01 reaches independently accepted H1, is:

- instrument set exactly `(xshe:000001,)`;
- no dynamic Universe query, selector, membership lookup, current listing fallback,
  symbol substitution, or survivorship claim;
- strategy family `PRECOMPUTED_TARGET` through schema-3 execution inputs;
- one precomputed target event whose exact position target is zero and whose
  canonical identity is bound into the request and execution input Bundle;
- initial and final position exposure zero;
- no orders, admissions, fills, fees, settlement obligations, cash/share corporate
  action dispatches, or position lots;
- accounting disposition exactly
  `ZERO_EXPOSURE_NO_ENTITLEMENT_NO_CORPORATE_ACTION_DISPATCH`;
- no claim that no corporate action existed; the disposition follows only from zero
  exposure and the exact no-trade case;
- two deterministic attempts, full trace, canonical v2 Result publication, and
  repository verification; and
- `deployment_authorized=false` throughout.

This simplification is allowed only because the production path still executes and
Integrity still owns grade. It is not execution-quality, fill, fee, liquidity,
strategy-alpha, listing, action-absence, or live-trading evidence.

## One execution Bundle, no hidden reads

The execution Bundle may have a different identity from the accepted G12I evidence
Bundle. It must be built and published through existing G12C/G12D and read through
the existing Market Data Reader. Its capabilities must exactly satisfy the accepted
BHA-01 Profile requirements and schema-3 execution contracts, and it must include the
accepted G12I stream unchanged:

- same stream key, capability/version, event type, event count, stream content hash,
  and ordered Event hashes;
- all 19 accepted G12I Events present as exact `MarketEvent` values, not copied
  summaries or rewritten availability;
- any Builder-owned projection has a new stream/Event identity and binds each source
  G12I Event hash directly;
- no resampling, aggregation, forward fill, synthetic missing Bar, nearby value,
  implicit role/capability fallback, or Runtime-created projection;
- no capability declared without an exact accepted Profile or schema-3 execution
  consumer and matching stream evidence;
- no second Bundle read, provider read, repository lookup, or cross-Bundle fallback
  during Runtime execution; and
- coverage/window bounds that permit every accepted G12I Event to be emitted at its
  exact `timeline_instant` before `end_exclusive`;
- one frozen zero-target decision UTC time strictly after the latest accepted G12I
  `available_time`, with its `SimulationInstant` strictly after every exact source
  `timeline_instant`; if a phase cut is also represented, every source phase is
  explicitly frozen before the zero-target decision phase; and
- no accepted G12I Event first consumed at or after the zero-target decision phase,
  and no post-decision source read or Timeline consumption.

BHA-02 must derive the minimum causal execution-Bundle contract from the immutable
BHA-01 component/Profile requirements and the existing schema-3 Runtime contracts.
If a provider-daily projection is genuinely required, BHA-02 owns its exact
event-time, availability-time, payload, purpose, source-hash, revision, and no-trade
lineage. It may not alter BHA-01 authority facts, and Runtime never resamples G12I.

## Production Run authority

The first accepted Run is generated once through the real
[`BacktestRuntime`](../../../../packages/backtest-runtime/src/crypto_quant_backtest/facade.py)
facade. It must reuse:

- schema-3 execution input hydration and retained one-Bundle replay;
- existing `ProfileResolver` and registry types;
- existing `AuditableBacktestRunner.for_v2()` two-attempt execution;
- existing `IntegrityEvaluator` requested/result grade policy;
- existing `CanonicalResultPublisher` atomic canonical-v2 publication; and
- existing `BacktestEvidenceRepository.load_completed()` verification.

The accepted evidence records exact request, resolved environment, Profile digests,
Build manifest, Bundle ref/manifest, execution semantic hash, semantic Run ID,
engine context, execution result, Integrity context/report, publication manifest,
and repository-verified publication identity.

Current `BacktestRuntime._publish_canonical()` sets both proof fields to `None`, so
unchanged Integrity blocks decision grade. Current Integrity checks only non-null
presence for those fields; it does not verify a proof body or recompute either claim.
Consequently BHA-03 is forbidden to mint a private facade hash, duplicate the same
implementation, or treat two same-implementation reconstructions as independent
proof.

Before BHA-01 may return H1, a separately and independently accepted generic
decision-grade rebuild/retention proof prerequisite must already exist. Its accepted
contract must provide a durable canonical proof body—not only a hash—under an exact
versioned schema; independent pre-Integrity verification/recomputation against
immutable execution-input, Bundle, PREP, Resolution, execution-case, attempt, and
attempt-evidence inputs; and `BacktestEvidenceRepository` replay of the same canonical
body and hash. It must preserve every existing v1 API and byte contract. This plan
does not design or implement that generic seam, assign it to G07, or accept its own
facade output as authority.

On hypothetical H1, BHA-03 only supplies provider-specific inputs and consumes that
already accepted implementation through the existing production path. It neither
generates proof nor writes `facade.py`, `integrity.py`, or
`local_market_bundle_reader.py`. `VerifiedCompletedPublicationV2` keeps its exact
exported constructor, fields, `from_finalized` behavior, root API, and bytes. BHA-03
may add an off-root provider-specific exact verified-run repository view by privately
reusing the existing `BacktestEvidenceRepository` completed verification path;
existing `load_completed()` behavior/signature remains exact, and no second
repository, parser, provider reader, or proof verifier is allowed.

## Runtime-owned assessment contract

BHA-04 owns one provider-specific, off-root Runtime assessor. The ADR-0008 assessment
is additive schema version `2`, implemented and fixtured only with v2 naming; every
existing v1 artifact/API/byte/hash/flag remains unchanged. It is pure, read-only, and
deterministic:

- no filesystem, network, environment, database, process, clock, repository, Reader,
  Builder, provider client, or I/O import;
- exact input types only, with deep reconstruction of all nested nominal values;
- exact G12I and G12K canonical bytes parsed with duplicate-key and invalid-constant
  rejection;
- Runtime-local nominal G12I/G12K report values; no Runtime→Builder import, open
  mapping, generic `ArtifactRef`, caller boolean, naked hash, or class-name check;
- constructor-bypass, subclass, duck type, nested substitution, missing/extra key,
  noncanonical byte, copied-hash, and inconsistent deterministic replay rejection;
- exact existing Integrity `RequestedResultGrade` and `ResultGrade` copied and bound,
  never minted, upgraded, downgraded, or re-evaluated;
- exact semantic Run, request, resolved context, engine context, Integrity report,
  Result, publication manifest/ref, and repository verification identities;
- exact execution Bundle ref/manifest and accepted G12I stream/Event membership;
- exactly one `TIMELINE_EVENT` trace entry for each accepted G12I
  `(event_id, event_hash, timeline_instant)` triple, with no missing, substituted,
  duplicated, or time/phase-shifted accepted entry;
- all 19 exact source Events strictly precede the frozen zero-target decision: its UTC
  time is after the latest G12I `available_time`, its `SimulationInstant` is after the
  latest exact source `timeline_instant`, and any represented source phase is
  explicitly prior; post-decision source consumption is rejected;
- exact singleton/no-dynamic-selector/zero-target/no-trade execution semantics;
- exact accounting disposition above; and
- `assessed_at >= max(g12i.observed_at, g12k.observed_at)`.

`assessed_at` is assessment metadata only. It cannot make a source Event visible,
change `MarketEvent.available_time`, extend the Run Timeline, repair a missing
`TIMELINE_EVENT`, or replace provider/acquisition availability.

### Assessment failure precedence

The outcome is exactly one assessment or one safe failure and never partial output.
First applicable code wins:

1. `INVALID_EXACT_INPUT_TYPE`;
2. `MALFORMED_OR_NONCANONICAL_BYTES`;
3. `G12I_RECONSTRUCTION_MISMATCH`;
4. `G12K_RECONSTRUCTION_MISMATCH`;
5. `PROFILE_AUTHORITY_MISMATCH`;
6. `EXECUTION_BUNDLE_MEMBERSHIP_MISMATCH`;
7. `SINGLETON_EXECUTION_CASE_MISMATCH`;
8. `RUN_CONTEXT_IDENTITY_MISMATCH`;
9. `INTEGRITY_GRADE_MISMATCH`;
10. `TIMELINE_CONSUMPTION_MISMATCH`;
11. `ACCOUNTING_DISPOSITION_MISMATCH`;
12. `ASSESSMENT_TIME_INVALID`;
13. `DIRECT_PREDECESSOR_INVALID`;
14. `ASSESSMENT_RECONSTRUCTION_MISMATCH`.

Failures contain only the code and canonical subject identities. They contain no raw
bytes, paths, token material, object repr, exception text, or partial authority.

## Append-only corrections and independent authority

Corrections never mutate accepted bytes, authority decisions, Profiles, Runs,
Results, publications, or assessments. The initial BHA-01 H1 decision authorizes only
the exact initial G12I/G12K identities in its body; it cannot authorize any corrected
source identity.

Any accepted source-identity change first requires a **new independently accepted
direct-successor BHA-01 authority decision**. That decision must bind the new exact
G12I/G12K identities and set `supersedes_decision_hash` (or an exact canonical
equivalent) to the immediately preceding accepted BHA-01 decision before any new
Profile registration, Resolution, Run, or assessment is allowed.

Current G12K schema version 1 pins the original accepted G12I identity. Therefore:

1. a G12I-only correction fails closed in the current assessor and is not a required
   successful path or acceptance fixture for this initial version;
2. G12I correction qualification remains blocked until a separately accepted
   upstream G12K successor lane rebinds the corrected G12I report/canonical-file/Event
   identities and directly supersedes the prior G12K report, followed by the new
   independently accepted BHA-01 direct-successor decision;
3. a G12K-only successor retaining the unchanged accepted G12I identity may be used
   only after its own upstream acceptance and the same new BHA-01 direct-successor
   authority step; and
4. every legal future correction then requires a new Profile semantic identity, a
   new execution Bundle when membership changes, a new production
   facade/PREP/Runner/Integrity Run, and a direct-successor assessment whose
   `supersedes_assessment_hash` binds the prior assessment.

Initial acceptance proves the initial assessment plus fail-closed rejection and
contract behavior for unaccepted, G12I-only, and missing-authority successors. A real
future correction acceptance is a separately reviewed upstream/authority/code/
governance fan-in, not current scope. A source correction cannot be attached to an
old Run or assessment, and a later timestamp alone is not a correction.

## Global failure/stop precedence

Execution stops at the first applicable boundary:

1. BHA-01 returns H2 because independently accepted applicable Profile/Build
   authority or the independently accepted generic durable proof prerequisite is
   missing;
2. BHA-02 cannot build an exact causal Bundle satisfying the accepted H1 Profile and
   existing schema-3 contracts;
3. ProfileResolver cannot resolve compatible exact Profile, Build, Bundle, and
   Environment inputs;
4. the accepted generic proof implementation is absent from the production path, its
   independent pre-Integrity verification fails, or repository replay of the same
   canonical proof body/hash fails;
5. facade/PREP/Runner/Integrity does not produce a repository-verifiable
   decision-grade canonical publication;
6. trace or accounting disposition does not match the exact case;
7. assessment reconstruction fails; or
8. BHA-05 governance/protected-artifact validation fails on either route.

No later node may waive or reinterpret an earlier stop.

## Authority map: one owner per fact

| Fact | Sole authority |
| --- | --- |
| Exact accepted G12I provider evidence and correction edge | accepted G12I plan/report bytes |
| Exact accepted G12K fixed-singleton evidence and correction edge | accepted G12K plan/report bytes |
| Exact applicable component/Profile/Build source authority inputs and every direct-successor source-identity authority decision | independently accepted Profile/Build prerequisite consumed by BHA-01 |
| Generic durable rebuild/retention proof schema, canonical body, independent verification/recomputation, production transport, and repository replay | separately and independently accepted prerequisite outside this G12M plan |
| Immutable identities of both accepted prerequisites and H1/H2 route decision | BHA-01 |
| Bundle/Build/Profile/Environment compatibility and resolved environment | existing Runtime `ProfileResolver` |
| Projection Events, complete execution Bundle membership, and G12D retention-proof identity | BHA-02 |
| Provider Profile registration, semantic Run, canonical publication, and provider-specific repository view | BHA-03 production journey |
| Requested/result grade | existing Runtime Integrity only |
| Source-to-Run qualification and assessment predecessor | BHA-04 assessor |
| H1-success or H2-blocked registry status and immutable receipt | BHA-05 governance fan-in |

## Dependency-typed DAG

```text
BHA-00 contract freeze ────────────────────────────────────┐
independently accepted applicable Profile/Build authority ─┤
independently accepted generic durable proof prerequisite ─┤
                                                           ▼
BHA-01 independent prerequisite-identity authority gate
   ├─ H2 ─× terminate BHA-02..BHA-04
   │          │ blocked decision
   │          └──────────────────────────────→ BHA-05 blocked governance fan-in
   └─ H1 (possible only after both prerequisites are accepted)
       ├────────────── direct authority evidence ──────────────┐
       │ immutable prerequisite identities                     │
       ▼                                                       │
BHA-02 Builder projection + complete execution Bundle          │
       │ contract + evidence                 ╲ direct Bundle hashes
       ▼                                      ╲                │
BHA-03 Profile registration + Resolution + production Run/Integrity publication
       │ canonical Run evidence                ╲ direct Run/proof-body/repository hashes
       ▼                                        ▼              ▼
BHA-04 pure Runtime schema-2 assessment ─────→ BHA-05 success governance fan-in
```

See the [execution DAG](g12m-tushare-fixed-singleton-qualification-v1/README.md)
for Ready states, typed edges, write conflicts, WIP policy, proof budget, and exact
write sets.

## Protected history

Untouched throughout this version:

- accepted G12I and G12K bytes, hashes, APIs, fixtures, and flags;
- accepted G12CD/G12H development artifacts;
- accepted Binance funding-history v1/v2 artifacts;
- accepted Binance H3 decision/report/manifest and terminated BHA branch;
- ADR 0008, all existing ResultGrade enums and meanings, exact
  `VerifiedCompletedPublicationV2`, every existing v1 artifact/API/byte contract,
  and the accepted generic proof prerequisite; and
- Binance H3 and unrelated Acceptance Matrix status.

This amended docs-only BHA-00 contract minimally reconciles the Acceptance Matrix to
Tushare `RESEARCH_GATE_REQUIRED` / code-not-ready status, including the missing
accepted generic durable proof seam as an exact controllable H2 condition. BHA-05 alone later records
the final H1-success or H2-blocked route status.

## Nonclaims

No general A-share universe, listing, survivorship, action absence, lifecycle
closure, permanent provider finality, provider completeness, live eligibility,
deployment authorization, legal/tax/compliance certification, nonzero strategy
performance, execution realism, generic provider framework, second registry,
second resolver, second repository, availability DSL, resampler, or cross-Bundle
reader is approved.
