---
id: G12M-TFS-BHA-05
status: BLOCKED_ROUTE
owner: governance single writer
produces:
  - immutable H1-success acceptance receipt and registry status
  - or immutable H2-blocked/terminated receipt and registry status
consumes:
  - immutable G12M-TFS-BHA-01 H1 authority evidence
  - direct typed G12M-TFS-BHA-02 H1 Bundle/proof hash evidence
  - direct typed G12M-TFS-BHA-03 H1 Run/accepted-proof/repository evidence
  - direct typed G12M-TFS-BHA-01 H1 authority evidence for BHA-04
  - G12M-TFS-BHA-04 H1 schema-2 assessment evidence
  - or immutable G12M-TFS-BHA-01 H2 with BHA-02 through BHA-04 terminated
depends_on:
  contract: [G12M-TFS-BHA-01-ROUTE, G12M-TFS-BHA-02-ON-H1, G12M-TFS-BHA-03-ON-H1, G12M-TFS-BHA-04-ON-H1]
  evidence: [route-specific canonical artifacts, direct BHA-02 Bundle hashes, direct BHA-03 Run/accepted-proof-body/repository hashes, reviews, validation logs, protected fingerprints]
  write_conflict: [acceptance-registry, g12-readme, main-branch]
---

# BHA-05 Governance and acceptance fan-in

## Outcome

BHA-05 is the sole governance fan-in for both legal routes:

- **H1 success:** record PASSED only after immutable independently accepted BHA-01 H1,
  the exact production Run, and the pure assessment are accepted; or
- **H2 blocked:** record only the immutable authority-incomplete decision,
  BHA-02-through-BHA-04 termination, and blocked registry status. Do not imply a
  Profile registration, Bundle, Run, Integrity result, assessment, or grade exists.

No other node writes the Acceptance Matrix or final route receipt.

## Route inputs

### H1 success

- immutable independently accepted BHA-01 H1 decision and manifest;
- direct typed BHA-02→BHA-05 evidence: Bundle/projection/report hashes, exact G12D
  retention-proof hash, and immutable publication identity;
- direct typed BHA-03→BHA-05 evidence: Profile/Build/request/Resolution/Run, the
  separately accepted generic proof-prerequisite identity, exact durable canonical
  proof-body/hash identity independently verified before Integrity and replayed by the
  repository, Integrity/publication/repository hashes, and the provider-specific
  verified-run evidence hash;
- direct typed BHA-01→BHA-04 authority evidence plus the BHA-04 initial assessment,
  null initial assessment predecessor, and fail-closed successor-contract evidence;
- focused/full validation and independent review receipts; and
- before/after fingerprints for all protected G12I/G12K/Binance artifacts.

### H2 blocked

- immutable independently accepted BHA-01 H2 decision and manifest;
- proof BHA-02, BHA-03, and BHA-04 are `TERMINATED_H2` with no outputs;
- documentation/status/link/diff/secret validation; and
- before/after fingerprints for all protected G12I/G12K/Binance artifacts.

H2 does not consume placeholder code-node tips.

## Exact write set

- `docs/implementation/acceptance-matrix.md`
- `../README.md`
- `../g12m-source-bounded-qualification-v1.md`
- `bha-02-builder-execution-bundle.md` status field
- `bha-03-production-profile-run.md` status field
- `bha-04-runtime-assessment.md` status field
- this directory's `README.md` DAG status and node-table states
- exactly one route receipt: `bha-05-h1-acceptance-receipt.md` on H1 or
  `bha-05-h2-blocked-receipt.md` on H2

No package, test, fixture, ADR, research, evidence decision, accepted G12I/G12K, or
Binance artifact edit. BHA-05 must create exactly one named route receipt and verify
the other is absent.

Status writes are route-atomic and non-conflicting:

- H1 sets BHA-02, BHA-03, and BHA-04 to `ACCEPTED_H1`, sets the DAG README status to
  `ACCEPTED_H1`, and writes only `bha-05-h1-acceptance-receipt.md`;
- H2 sets BHA-02, BHA-03, and BHA-04 to `TERMINATED_H2`, sets the DAG README status to
  `BLOCKED_H2`, and writes only `bha-05-h2-blocked-receipt.md`; and
- no route may leave a prior blocked/terminated/accepted state that conflicts with
  the selected fan-in or mix H1 and H2 statuses.

## H1 acceptance checks

1. graph is acyclic and every consumed node is an immutable accepted tip;
2. BHA-01 is independently accepted only after both the applicable Profile/Build
   authority and generic durable proof prerequisites are independently accepted; it
   binds their immutable identities, and no G12M/assessor/proof-to-Profile/Build
   authority edge exists;
3. existing Resolution accepted the exact Bundle/Build/Profile/Environment inputs;
4. complete Bundle contains exact accepted G12I membership and no excess capability;
5. production facade/PREP/Runner/Integrity/canonical-publication path is evidenced;
6. the separately accepted generic proof prerequisite provides a durable canonical
   proof body, exact versioned schema, independent pre-Integrity verification/
   recomputation against immutable execution-input/Bundle/PREP/Resolution/case/
   attempt/attempt-evidence inputs, repository replay of the same body/hash, and v1
   API/byte preservation; BHA-01 only binds its immutable accepted identity and BHA-03
   only consumes it through the existing production path;
7. no facade-generated opaque hash, including after two same-implementation
   reconstructions, can satisfy acceptance merely because Integrity checks non-null
   presence; no caller or G12M input can bootstrap proof or grade;
8. Integrity policy is unchanged and Integrity alone supplied the exact
   requested/result grade;
9. evidence repository verifies the accepted publication and replays the same
   canonical proof body/hash through its existing path, preserves exact
   `VerifiedCompletedPublicationV2` API/behavior/bytes, and supplies the off-root
   provider-specific verified-run evidence without a second repository or parser;
10. all 19 accepted G12I `(event_id, event_hash, timeline_instant)` triples have
   exactly one matching `TIMELINE_EVENT`; the decision UTC time is after the latest
   source `available_time`, its `SimulationInstant` is after every source
   `timeline_instant`, every represented source phase is prior, and there is no
   post-decision source consumption;
11. exact singleton/no-selector/zero-target/accounting disposition passes;
12. assessment is Runtime-owned, additive schema version 2, pure,
    exact-type/constructor-bypass safe, Builder-free, and only binds
    BHA-01/Resolution/Integrity outcomes; all v1 artifacts/APIs remain unchanged;
13. `assessed_at` is valid but did not replace Runtime availability;
14. initial acceptance includes initial assessment success and fail-closed rejection
    of G12I-only correction, unaccepted G12K successor, and any source change lacking
    a new independently accepted BHA-01 direct-successor decision; current G12K v1
    pins original G12I, so no successful correction path is required or faked, and
    future real correction acceptance is a separate fan-in;
15. accepted Binance H3 and v1/v2 artifacts are unchanged;
16. BHA-02/BHA-03/BHA-04 and DAG statuses are atomically `ACCEPTED_H1`, exactly
    `bha-05-h1-acceptance-receipt.md` exists, and the H2 receipt is absent;
17. this current BHA-00 status-authority reconciliation remains accurate until
    BHA-05 writes the final H1/H2 status; and
18. links, Markdown, Ruff/Pyright, focused/full tests, import boundaries, lock, diff,
    gitleaks, and independent final review pass.

## H2 blocked checks

1. BHA-01 H2 is immutable, independently accepted, and identifies either an exact
   applicable controllable component/Profile/Build authority gap or the missing/not-
   accepted generic durable rebuild/retention proof prerequisite at current HEAD;
2. missing strict G12H successor, official, or legal closure alone was not treated as
   H2 contrary to ADR 0008;
3. BHA-02 through BHA-04 are `TERMINATED_H2` and produced no package, test, fixture,
   Bundle, Profile registration, Run, publication, or assessment output;
4. BHA-02/BHA-03/BHA-04 are atomically `TERMINATED_H2`, the DAG is `BLOCKED_H2`,
   exactly `bha-05-h2-blocked-receipt.md` exists, and the H1 receipt is absent;
5. the registry and receipt say blocked/terminated, not accepted or decision-grade;
6. protected G12I/G12K/Binance bytes are unchanged; and
7. links, Markdown, route/status consistency, diff, gitleaks, and independent final
   review pass.

## Failure precedence

1. unaccepted or mutable BHA-01 route decision;
2. H1/H2 route mixing or illegal code-node output on H2;
3. protected-byte mismatch;
4. authority/proof/Resolution/grade bootstrap finding;
5. on H1, Bundle/Event/trace or production-path/repository-verification gap;
6. on H1, accounting/time/correction mismatch;
7. test/architecture/static-validation failure where applicable;
8. documentation/link/registry inconsistency; or
9. secret finding.

Any failure leaves G12M Tushare unaccepted. Do not partially update the registry.

## Nonclaims

Either route remains fixed-singleton, source-bounded, historical, no-trade, and
non-deployment. General A-share listing/universe/survivorship/corporate-action
closure, strict official/legal closure, provider finality/completeness, nonzero
execution, legal certification, live use, and Binance qualification remain unchanged.
