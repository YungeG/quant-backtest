---
id: G12M-SOURCE-BOUNDED-QUALIFICATION-V1
readiness: BLOCKED
gate_status: DRAFT
owner: backtest-runtime qualification
produces:
  - future provider-bounded G12M implementation contract
consumes:
  - ADR 0008
  - accepted G12I SZSE evidence slice
  - accepted G12K SZSE/CNINFO evidence slice
  - accepted Binance FAPI observed-as-of evidence slice
depends_on:
  contract: [G07, G12I, G12K, G12L-*]
  evidence: [exact canonical upstream artifacts and accepted hashes from the three named lanes]
  write_conflict: [runtime-integrity-policy, acceptance-registry]
---

# G12M source-bounded qualification readiness

## Outcome

Prepare a future Runtime-owned, read-only qualification of an already graded
backtest result under [ADR 0008](../../../adr/0008-source-bounded-decision-grade.md).
Do not freeze or authorize a production interface until the provider lanes below
publish exact accepted canonical artifacts and hashes.

## Status

`DRAFT / BLOCKED`. ADR 0008 policy is accepted. G12M implementation readiness is
blocked because the repository does not yet contain Runtime-verifiable source
evidence contracts for the selected Tushare/SZSE, SZSE/CNINFO, and Binance FAPI
slices.

No production code, public type, function signature, serialized assessment body,
failure enum, test contract, or write set is authorized by this plan.

## Decision frozen now

ADR 0008 is the only frozen decision:

- Tushare and Binance remain the sole market-data providers;
- source-bounded decision grade is allowed when all controllable evidence passes;
- impossible provider assurances remain explicit limitations rather than ordinary
  historical-backtest blockers;
- existing `RequestedResultGrade`, `ResultGrade`, v1 artifacts, canonical bytes,
  hashes, flags, and APIs remain unchanged;
- G12M never mints, derives, upgrades, or downgrades run grade;
- correction handling is append-only: new source evidence and a new assessment,
  with old runs/results immutable and auditable; and
- legal/tax/compliance certification and live/deployment authorization remain
  separate claims owned outside G12M.

ADR 0008 does not modify ADR 0004, ADR 0007, or frozen G12H artifacts.

## Premature interface rejected

The previously proposed generic Runtime `Mapping`/`ArtifactRef` assessor is not
honest enough to freeze:

1. Runtime has no importable source verifier for the Builder/provider artifacts
   that would establish raw-byte retention, acquisition receipt, scope,
   observed-as-of, normalization, publication, and correction identity.
2. `SourceSnapshot.to_canonical_dict()` intentionally omits `archive_bytes`.
   Rehashing its canonical body cannot prove possession or verification of the
   raw provider bytes.
3. Generic caller mappings, booleans, and hashes can self-attest that upstream
   work passed. Canonical shape alone cannot turn those assertions into evidence.

Therefore a naked hash, generic `ArtifactRef`, caller boolean, or open-ended
mapping must not qualify a result. Adding a Runtime-side generic verifier would
either duplicate Builder authority or trust claims it cannot verify.

## Prerequisite source lanes

| Lane | Exact evidence contract still needed before G12M design | Acceptance identity still needed |
| --- | --- | --- |
| G12I SZSE | Finite SZSE/Tushare price-purpose, availability, missing-data, no-lookahead, normalization, and publication evidence with exact observed-as-of semantics and a Runtime-consumable canonical boundary. | Accepted artifact type/schema, canonical bytes, content hashes, source/scope bindings, and immutable acceptance commit. |
| G12K SZSE/CNINFO | Finite listing/universe and corporate-action evidence that binds SZSE/CNINFO source bytes, receipts, point-in-time scope, corrections, and supported completeness limits. | Accepted catalog/action artifact types, canonical hashes, correction identities, scope hash, and immutable acceptance commit. |
| Binance FAPI observed-as-of | Finite Binance FAPI acquisition evidence that binds the exact request/response bytes, receipt-derived observed-as-of, local identity, normalization/publication boundary, and known archive limitations. | Accepted source/receipt/report artifact types, exact canonical hashes, request/scope identity, observed-as-of rule, and immutable acceptance commit. |

Research notes, ad hoc files, inherited hash claims, development fixtures, or
Builder objects without an accepted canonical cross-package boundary do not
unblock G12M.

## Readiness exit criteria

G12M may move from `BLOCKED` only after all three lanes provide:

1. exact provider, dataset, finite scope, source authority, and observed-as-of
   semantics;
2. canonical artifacts whose accepted hashes bind the retained provider evidence
   and the relevant normalized/published scope;
3. a verifier or nominal value boundary that Runtime can consume without
   importing Builder or performing I/O;
4. explicit limitation semantics for unavailable permanent identity, revision
   finality, provider scope completeness, and joined Binance funding evidence;
5. append-only correction identity sufficient to distinguish a new snapshot from
   the superseded evidence; and
6. accepted tests, architecture checks, immutable commit identities, and review
   closure owned by each upstream lane.

Only then may a new G12M contract freeze exact inputs, output artifact, failure
precedence, compatibility rules, tests, and implementation write set. That
contract must bind the accepted finite artifacts directly; it must not introduce
a provider registry, generic source framework, facts registry, or policy DSL.

## Future invariants

Any later G12M implementation must preserve these boundaries:

- Runtime ownership, pure read-only assessment, and no filesystem/network/
  repository access;
- no Runtime→Builder import and no provider client;
- one exact existing completed Integrity result remains the sole run-grade
  authority;
- a development result cannot be promoted by source qualification;
- provider evidence is accepted only through the exact upstream artifacts and
  hashes frozen by the prerequisite slices;
- source-bounded qualification remains independent of legal/live/deployment
  authority; and
- prior artifacts and results remain immutable after correction discovery.

## High-level acceptance outcome

A future accepted G12M slice must demonstrate, for at least one exact finite
provider case, that an existing decision-grade completed result can be bound to
accepted source evidence without regrading the run, importing Builder, doing I/O,
or trusting caller self-attestation. It must also demonstrate fail-closed
rejection of substituted source, scope, time, or correction identity and preserve
all protected v1 bytes and hashes.

## Remaining controllable blockers

Even under ADR 0008, these remain real blockers once exact contracts exist:

- missing retained raw provider evidence or acquisition receipt;
- missing or open-ended provider/request scope;
- missing or invalid observed-as-of evidence;
- lookahead;
- unclassified missing data;
- non-deterministic normalization, publication, or replay;
- spoofed or inconsistent source/scope/run identity;
- absent accepted Bundle/Build/Profile/Environment/Integrity result evidence;
- invalid append-only correction identity; and
- missing Promotion/operations authorization for a live/deployment claim.

Provider permanent identity, proof of no future revision, provider-complete
universe/scope, and immutable joined Binance funding archives remain limitations,
not ordinary source-bounded historical-research blockers.

## Nonclaims

No generic assessor, public Runtime interface, new grade, provider registry,
source framework, facts registry, policy DSL, legal certification, live trading,
deployment authorization, or provider-global completeness claim is approved.
