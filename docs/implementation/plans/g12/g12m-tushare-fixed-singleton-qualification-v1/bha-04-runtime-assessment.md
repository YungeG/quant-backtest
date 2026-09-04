---
id: G12M-TFS-BHA-04
status: TERMINATED_H2
owner: provider-specific Runtime assessor writer
produces:
  - pure read-only Tushare fixed-singleton assessment schema version 2
  - canonical v2 failure and fail-closed successor-contract artifacts
consumes:
  - immutable independently accepted G12M-TFS-BHA-01 H1
  - G12M-TFS-BHA-02
  - G12M-TFS-BHA-03
  - exact accepted G12I/G12K canonical bytes
depends_on:
  contract: [G12M-TFS-BHA-01-H1, G12M-TFS-BHA-02, G12M-TFS-BHA-03]
  evidence: [direct typed independently accepted BHA-01 authority decision, accepted source bytes, repository-verified canonical Run]
  write_conflict: []
fan_in: G12M-TFS-BHA-05
---

# BHA-04 Assess exact source-to-Run qualification

## Outcome

Implement one off-root Runtime assessor for the exact Tushare fixed-singleton case.
The ADR-0008 qualification is additive schema version `2`, with exact canonical type
`g12m_tushare_fixed_singleton_source_bounded_assessment_v2` and an exact Runtime value named
`TushareFixedSingletonSourceBoundedAssessmentV2`. It reports whether
already-accepted provider evidence and immutable BHA-01 authority identities match
an already-resolved, already-graded, repository-verified production Run. It does not
decide Profile/Build eligibility, Resolution compatibility, execution, or grade.

All existing v1 artifacts, APIs, canonical bytes, hashes, flags, fixtures, and
consumer behavior remain unchanged. This node neither mutates nor reinterprets a v1
assessment; correction/supersession edges are within the additive v2 assessment
line.

## Inputs

- immutable independently accepted BHA-01 H1 decision and manifest identity;
- exact canonical G12I report bytes;
- exact canonical G12K report bytes;
- exact BHA-02 execution Bundle manifest and Event tuple;
- exact off-root provider-specific verified-run evidence from BHA-03, produced by the
  existing repository's private completed-publication verification path after replay
  of the same independently accepted canonical proof body/hash;
- exact `assessed_at` nominal UTC value; and
- either no predecessor assessment or the exact direct predecessor assessment.

All inputs are already in memory. The assessor performs no I/O and imports no
Builder.

## Nominal reconstruction

Runtime-local closed nominal values mirror every G12I and G12K report field and
recompute all deterministic identities. Parsing rejects duplicate keys, invalid
constants, noncanonical bytes, unknown/missing keys, open mappings, subclass/duck
values, constructor bypass, nested substitution, copied hashes, inconsistent row
replay, or any true upstream qualification flag.

The assessor independently reconstructs both reports and cross-checks G12K's embedded
G12I identities against the independently reconstructed G12I value.

## Run and Bundle binding

Require exact:

- provider, dataset, scope, instrument, observed-at, report, canonical-file, and
  direct source predecessor identities;
- execution Bundle ref/manifest, exact G12I stream membership, and the capabilities
  already accepted by ProfileResolver for the BHA-01-authorized registrations;
- singleton request and no dynamic selector;
- zero precomputed target, initial/final exposure, orders, fills, fees, settlement,
  lots, and corporate-action dispatch;
- semantic Run, request, resolved environment, Profile, Build, execution semantic,
  engine context, independently accepted proof-prerequisite and canonical proof-body/
  hash identities, Integrity context/report, Result, publication, and repository
  identities;
- exact BHA-01 authority identity and existing Resolution compatibility outcome,
  copied without reevaluation;
- existing Integrity requested/result grade exactly, copied without evaluation; and
- exactly one `TIMELINE_EVENT` trace entry for every accepted G12I
  `(event_id, event_hash, timeline_instant)` triple;
- the frozen zero-target decision UTC time and `SimulationInstant`: UTC time strictly
  after the latest G12I `available_time`, `SimulationInstant` strictly after every
  source `timeline_instant`, and every represented source phase explicitly prior,
  with all 19 exact source Events in the prior causal cut; and
- no accepted source Event consumed first at or after the decision phase.

`assessed_at` is not earlier than either source observed-at. It does not repair late
or absent Runtime availability, move an Event to an earlier phase, or authorize
post-decision source consumption.

## Assessment body

The canonical success body binds at least:

```text
type=g12m_tushare_fixed_singleton_source_bounded_assessment_v2
schema_version=2
fixed case key/version
G12I report and canonical-file identities
G12K report and canonical-file identities
immutable BHA-01 authority identity binding both accepted prerequisites
accepted generic proof-prerequisite and canonical proof-body/hash identities
Profile/Build/resolved-environment and compatibility-report identities
execution Bundle ref/manifest and exact G12I Event-hash tuple
semantic Run/request/context/execution/Integrity/Result/publication identities
requested grade and result grade
TIMELINE_EVENT `(event_id,event_hash,timeline_instant)` consumption hash
frozen zero-target decision instant/phase and strict prior-source causal-cut hash
zero-exposure accounting disposition hash
assessed_at
supersedes_assessment_hash
limitations and nonclaims
deployment_authorized=false
assessment_hash
```

The assessment does not copy raw provider bytes or serialize secrets, paths,
exceptions, object repr, or mutable repository state.

## Failure precedence

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

Exactly one failure is returned with canonical subject identities and no partial
assessment.

## Corrections

Initial assessment has `supersedes_assessment_hash=null` and accepts only the exact
initial G12I/G12K identities bound by the initial independently accepted BHA-01 H1.
That H1 cannot authorize corrected source identities.

Current G12K schema version 1 pins the original G12I identity. Therefore this initial
assessor must fail closed on every G12I-only correction; it must not fabricate or test
a successful G12I correction path. Qualification of a future G12I correction remains
blocked until a separately accepted upstream G12K successor lane rebinds the corrected
G12I identities, followed by a separately independently accepted BHA-01 direct-
successor decision binding both source identities and the prior authority decision
through `supersedes_decision_hash` (or an exact canonical equivalent).

A G12K-only successor retaining unchanged G12I is likewise ineligible until its own
upstream acceptance and that new BHA-01 direct-successor decision. Only after those
future prerequisites may a separate fan-in require a new Profile semantic identity,
new Bundle when membership changes, new production Run, and direct-successor
assessment with `supersedes_assessment_hash` binding the prior assessment. That real
correction acceptance is not current scope. Current acceptance proves initial success
plus rejection/contract behavior for G12I-only, unaccepted-upstream, missing-authority,
old-Run, and nondirect-predecessor cases.

## Exact write set

- `packages/backtest-runtime/src/crypto_quant_backtest/g12m_tushare_fixed_singleton_assessment_v2.py`
- `tests/runtime/g12m/test_tushare_fixed_singleton_assessment_v2.py`
- `tests/architecture/test_g12m_tushare_fixed_singleton_assessment_boundary.py`
- `tests/fixtures/runtime/g12m-tushare-fixed-singleton-assessment-v2/`

No Runtime root export, shared resolver/registry/repository, Builder, Market Data
Reader, Kernel, canonical Run fixture mutation, Acceptance Matrix, G12 README, or any
v1 artifact/API/fixture edit.

## Acceptance

- exact additive schema-2 success reconstruction from production Run evidence, with
  schema/type mutation rejection and all v1 artifacts/APIs unchanged;
- one adversarial test for every precedence class and constructor-bypass layer;
- exact 19-Event `(event_id, event_hash, timeline_instant)` consumption, strict
  pre-decision causal cut, and duplicate/missing/substitution/time-shift/post-decision
  rejection;
- BHA-01 authority and Resolution outcomes are copied/bound, not decided; requested/
  result grade is copied exactly and development grade cannot become success;
- accounting disposition and nonclaims remain exact;
- initial success plus fail-closed G12I-only correction, unaccepted G12K successor,
  and missing BHA-01 direct-successor authority tests; no successful correction path
  is required or faked in this initial version;
- architecture test proves no Builder/I/O imports; and
- focused/adjacent Runtime, full acceptance suite, Ruff/Pyright, diff, gitleaks, and
  independent source/grade/time/accounting reviews pass.
