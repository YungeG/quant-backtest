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

`DRAFT / BLOCKED`. ADR 0008 policy is accepted. The exact G12I Tushare/SZSE
nominal reconstruction boundary below is now frozen. G12M implementation readiness
remains blocked because the repository does not yet contain accepted exact
SZSE/CNINFO G12K and Binance FAPI observed-as-of source evidence contracts.

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
| G12I SZSE | `ACCEPTED`: exact July-2026 Tushare `daily`/`trade_cal`/`suspend_d` observation report, canonical replay, append-only correction identity, and nominal Runtime boundary below. | Source `4389877b8879fc9bb1a6d6544c4079a7d29312ab`; report `sha256:ff09c4ad9f8025e66689387b5132d3d85c4101276fbf7330dd5040af111cc029`; canonical file `sha256:9cbfc115e41f56d1e83eac520856c3f529f83972b97111238e5dbb1a68c4eae6`. |
| G12K SZSE/CNINFO | Finite listing/universe and corporate-action evidence that binds SZSE/CNINFO source bytes, receipts, point-in-time scope, corrections, and supported completeness limits. | Accepted catalog/action artifact types, canonical hashes, correction identities, scope hash, and immutable acceptance commit. |
| Binance FAPI observed-as-of | Finite Binance FAPI acquisition evidence that binds the exact request/response bytes, receipt-derived observed-as-of, local identity, normalization/publication boundary, and known archive limitations. | Accepted source/receipt/report artifact types, exact canonical hashes, request/scope identity, observed-as-of rule, and immutable acceptance commit. |

Research notes, ad hoc files, inherited hash claims, development fixtures, or
Builder objects without an accepted canonical cross-package boundary do not
unblock G12M.

## Frozen G12I nominal reconstruction boundary

A future G12M Runtime implementation may consume the accepted G12I evidence only as
exact canonical bytes for type
`tushare_cn_a_share_daily_source_bounded_observation_report`, schema version `2`.
It must use a closed nominal Runtime value that mirrors every accepted report field;
it must not import Builder, accept an open mapping, generic `ArtifactRef`, caller
boolean, class-name assertion, or naked hash.

Reconstruction must reject noncanonical JSON, duplicate/extra/missing keys,
constructor bypass, nested type substitution, and any mismatch in the fixed provider,
datasets, instrument, XSHE/SZSE UTC scope, 51 ordered member identities/times, date
partition, limitations, false qualification flags, or null first-capture
`supersedes_report_hash`. It must recompute the complete report hash, reconstruct the
one-stream `MarketBundleManifest` from the bound manifest/stream/Event fields, and
require `MarketBundleRef.from_manifest()` identity. It must also bind these accepted
identities:

- receipt `sha256:95ba0d8e28414aa997e232c90eee03318f13f2c9041b36f4da046bbc5b2fb623`;
- snapshot `sha256:9f1915e302e1a1f5b74a2cdccb54c08676642da3b48642eb9bbf728dc4c98f2e`;
- content tree `sha256:ef44ecd44476dcd3d1cd69f82305df29d186c82350c45f427b5bf008b62d57af`;
- provenance `sha256:4dba800ca4688504c804009bcb21a4698cc431761be6847a81bfeef02a0e05e4`;
- manifest body `sha256:87e1209b5510e9d5489d414e63c1008117282a57e1d05555113103222f06a505`;
- Bundle ref manifest `sha256:d9f73a48eeb8b92600cd7fdd9017ba8b0536654cb466ce57c8bc6695f10271df`;
- stream `sha256:da735d4545e458f8bb1432008b89e45b7c820812f0fed91ebc6610721ad491a1`;
- execution-reference requirement `sha256:9a4d38330cc1048cc5c7181d67614585e0d47f63f6a51e8ce8ed66b5488bbfcb`;
- valuation requirement `sha256:14a2f05bcaf6edc8540fd3ce1e850a04af5fb0e5a8405154ba1ab41d4faf5a6d`;
- report `sha256:ff09c4ad9f8025e66689387b5132d3d85c4101276fbf7330dd5040af111cc029`;
- canonical report file `sha256:9cbfc115e41f56d1e83eac520856c3f529f83972b97111238e5dbb1a68c4eae6`.

This freezes no Runtime function signature or public export. A later corrected G12I
capture is a new upstream acceptance and must bind its predecessor through
`supersedes_report_hash`; it cannot silently replace these identities.

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
