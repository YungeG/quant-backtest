---
id: G12M-TFS-BHA-01
status: DECIDED_H2
owner: independent prerequisite-identity authority lane
produces:
  - immutable H1 binding accepted applicable component/Profile/Build and durable-proof prerequisite identities
  - or immutable H2 prerequisite-incomplete decision
consumes:
  - G12M-TFS-BHA-00 exact case boundary
  - accepted G12I/G12K evidence identities
  - separately independently accepted applicable component/Profile/Build authority
  - separately independently accepted generic durable rebuild/retention proof prerequisite
depends_on:
  contract: [G12M-TFS-BHA-00, ADR-0008]
  evidence:
    - exact applicable first-party component/Profile/Build authority
    - accepted generic durable rebuild/retention proof prerequisite identity and acceptance manifest
  write_conflict: [profile-resolution-build-and-proof-prerequisite-decision]
fan_in: [G12M-TFS-BHA-02, G12M-TFS-BHA-03, G12M-TFS-BHA-04, G12M-TFS-BHA-05]
---

# BHA-01 Bind independently accepted Profile/Build and durable-proof prerequisites

## Outcome

This prerequisite lane is owned independently of G12M and its assessor. It returns
exactly one immutable, independently accepted decision:

- **H1 — EXACT_PREREQUISITES_ACCEPTED:** both (a) the exact applicable controllable
  component/Profile-registration/immutable-Build authority and (b) a separately and
  independently accepted generic decision-grade durable rebuild/retention proof seam
  already exist and their immutable acceptance identities are bound; or
- **H2 — PREREQUISITE_INCOMPLETE:** either prerequisite is missing or not independently
  accepted. BHA-02 through BHA-04 terminate and BHA-05 becomes the sole blocked
  governance fan-in.

The generic proof prerequisite must already provide a durable canonical proof body,
not only a hash; an exact versioned schema; independent pre-Integrity verification and
recomputation against immutable execution-input, Bundle, PREP, Resolution, case,
attempt, and attempt-evidence inputs; repository replay of the same canonical body
and hash; and preservation of all existing v1 APIs and bytes. BHA-01 only consumes and
binds that accepted prerequisite identity. It does not design, implement, recompute,
or self-attest the seam, and this plan does not invent a generic G07 implementation.

H1 supplies immutable prerequisite identities; it does not resolve a request, declare
a Bundle compatible, generate proof, or assign a result grade. At execution time the
existing `ProfileResolver` remains sole authority for Bundle/Build/Profile/Environment
compatibility, the accepted generic seam independently verifies proof before
Integrity, and existing Integrity remains sole requested/result-grade authority.
G12M and BHA-04 may only bind those outcomes.

The accepted H2 decision records that both the applicable Profile/Build authority
and the independently accepted generic durable proof seam are absent.

## Questions that must close separately

1. Which exact Market, Simulation, and Execution Account component facts are
   applicable to the fixed singleton, zero-target, zero-exposure, no-trade case?
2. Which exact source authorities support those applicable facts and the resulting
   additive Profile registration inputs without reusing DEVELOPMENT qualification?
3. Which current China A-share limitations are genuinely inapplicable to this exact
   case, which remain explicit limitations/nonclaims, and which are controllable
   requirements of an actually selected production component?
4. What immutable Build artifacts, roles, install modes, content identities, and
   source identities can be presented to Resolution for this exact Profile?
5. Which required Bundle capabilities and component ports are declared by the exact
   selected Profile registrations? BHA-02 owns satisfying them; Resolution owns the
   runtime compatibility decision.
6. How do the exact accepted G12I/G12K report identities enter Profile semantic
   identity so an accepted correction forces a new semantic Run without
   making provider evidence a Profile or grade authority?
7. What immutable acceptance identity proves that the separate generic durable proof
   prerequisite is already accepted with its exact schema/body verification and
   repository-replay contract, without BHA-01 designing or self-attesting it?

Missing strict G12H successor, official, or legal closure alone is not H2. ADR 0008
permits strict closure to remain unknown for normal source-bounded historical
research. Record it as a limitation and nonclaim unless an exact production component
selected for this case has a controllable contract that genuinely requires that
specific closure. The current-selected DEVELOPMENT G12H/Profile artifacts cannot
answer that question or self-authorize decision-grade eligibility.

## H1 required body

The canonical H1 decision binds only:

- the fixed instrument, no-selector, zero-target, zero-exposure case boundary;
- the immutable acceptance identity and manifest hash of the independently accepted
  generic durable rebuild/retention proof prerequisite, including its exact accepted
  schema version identity, without copying or redesigning its proof body;
- exact selected component refs and the applicable fact/limitation disposition for
  each component;
- exact Market/Simulation/Account registration keys, versions, digests, requested
  grade declarations, decision-grade eligibility inputs, and required capabilities;
- exact immutable Build roles, install modes, content/source identities, and
  decision-grade eligibility inputs;
- exact accepted source identities used in Profile semantic identity;
- `supersedes_decision_hash=null` for this initial decision; every future source-
  identity change requires a separately and independently accepted direct-successor
  BHA-01 decision that binds the new exact G12I/G12K identities and the immediately
  preceding accepted decision hash before Profile/Run/assessment work;
- explicit strict-closure limitations/nonclaims and any exact selected-component
  requirement that makes a controllable closure fact applicable; and
- explicit nonclaims.

The decision must not contain a proof design or generated proof, resolved environment,
compatibility result, Integrity issue/result, G12M qualification, projection
algorithm, execution Bundle, Run, publication, or assessment. G12I/G12K report hashes
may be semantic source bindings, but accepted provider evidence cannot itself set
Profile or Build eligibility. Initial H1 authorizes only the identities in that
initial decision; it is never inherited by a corrected source identity.

Current G12K v1 embeds the original accepted G12I identity. BHA-01 must not claim an
available G12I-correction route from that artifact. A future G12I correction remains
blocked until a separately accepted upstream G12K successor rebinds it; a G12K-only
successor must likewise be independently accepted upstream. Either future route then
requires a new BHA-01 direct-successor decision with `supersedes_decision_hash` (or
an exact canonical equivalent). That future authority and governance fan-in is not
part of this initial H1/H2 decision.

## Exact write set

- `docs/research/g12m-tushare-fixed-singleton-prerequisite-authority-v1.md`
- `evidence/g12m-tushare-fixed-singleton-prerequisite-authority-v1/decision.json`
- `evidence/g12m-tushare-fixed-singleton-prerequisite-authority-v1/manifest.sha256`

No G12M assessor, package, test, fixture, Profile registration, Builder Bundle, proof
schema/body/generator/verifier/repository implementation, Resolution or Integrity
implementation, Acceptance Matrix, G12 README, or accepted artifact edit.

## Failure precedence

1. target scope or singleton/no-selector mismatch;
2. generic durable rebuild/retention proof prerequisite is missing, mutable,
   self-attested, hash-only, lacks the accepted exact versioned canonical body, lacks
   independent pre-Integrity recomputation, fails to bind immutable execution
   evidence, lacks repository replay of the same body/hash, or changes v1 APIs/bytes;
3. applicable component fact is unowned or unsupported;
4. Profile-registration authority input is missing or development-only;
5. immutable Build identity or eligibility input is missing;
6. selected Profile component/capability contract is inconsistent;
7. source-report semantic binding is incomplete;
8. a selected production component has an unmet applicable controllable closure
   requirement; or
9. canonical decision reconstruction mismatch.

Any applicable failure yields H2. Unknown strict/legal closure that is not required by
an exact selected component remains a limitation/nonclaim, not a failure. No
provisional H1, placeholder authority, waiver, or "development for now" branch
exists.

## Acceptance

- every H1 fact names its sole first-party/source-bounded authority and hash;
- H1 exists only after independently accepted applicable Profile/Build authority and
  independently accepted generic durable rebuild/retention proof prerequisites both
  exist;
- the proof prerequisite has a durable canonical body, exact versioned schema,
  independent pre-Integrity verification/recomputation against immutable execution
  evidence, repository replay of the same body/hash, and v1 API/byte preservation;
- BHA-01 binds only its immutable accepted identity and does not design, implement,
  generate, recompute, or self-attest proof;
- the decision was accepted independently of G12M and is immutable before BHA-02 or
  BHA-03 consumes it;
- current DEVELOPMENT Profile/G12H artifacts are rejected as eligibility authority;
- Resolution, not BHA-01 or G12M, owns runtime compatibility and eligibility;
- Integrity remains sole requested/result-grade authority;
- strict closure unknown is a limitation/nonclaim unless an exact selected component
  proves it applicable;
- initial H1 binds only the initial G12I/G12K identities with a null decision
  predecessor, while mutation to either source identity fails without a separately
  accepted direct-successor authority decision;
- decision JSON round-trips canonically and manifest hashes match; and
- independent Profile, Resolution, Build, and authority-boundary reviews pass.
