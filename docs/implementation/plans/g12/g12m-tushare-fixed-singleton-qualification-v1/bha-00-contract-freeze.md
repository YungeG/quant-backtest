---
id: G12M-TFS-BHA-00
status: CONTRACT_COMPLETE
owner: qualification contract single writer
produces:
  - accepted exact fixed-singleton contract
  - protected-history fingerprint baseline
consumes:
  - parent plan
  - current HEAD Runtime/Builder/Market Data seam findings
depends_on:
  contract: [G12M-SOURCE-BOUNDED-QUALIFICATION-V1, ADR-0008]
  evidence: [accepted G12I and G12K canonical identities]
  write_conflict: [g12m-plan-tree]
fan_in: G12M-TFS-BHA-01
---

# BHA-00 Freeze the exact qualification contract

This docs-only plan commit completed BHA-00. At that historical freeze point, the
independently owned BHA-01 Profile/Resolution/Build authority lane was the sole
eligible next node. BHA-01 later reached `DECIDED_H2`; BHA-05 accepted that route as
`ACCEPTED_H2`. BHA-00 remains `CONTRACT_COMPLETE`.

## Outcome

Accept the parent plan as the sole contract for this provider-specific case and
record protected byte fingerprints before any research or code work.

## Required findings

Confirm from current HEAD that:

- G12I is one `tushare_cn_a_share.daily-publications@1` stream with 19 Events and
  false qualification flags;
- G12K is fixed `xshe:000001`, 96 retained rows, zero target-relevant rows, and no
  listing/survivorship/action-absence/finality authority;
- `CnAShareResolvedProfile` is DEVELOPMENT and exact-reconstructs false eligibility
  flags, so it cannot self-authorize the independent H1 prerequisite;
- the schema-3 multi-resolution preparation path requires `price_bars@1` for its
  declared observation bindings; the current DEVELOPMENT China A-share simulation
  Profile requires `bar_open@1`; and accepted G12I supplies neither capability while
  its Event availability is later than its July event time;
- ADR 0008 permits strict official/legal closure to remain unknown unless an exact
  selected production component makes a controllable closure fact applicable;
- the facade already owns schema-3 PREP, resolver, Runner, Integrity, canonical
  publication, and evidence-repository flow, but current
  `BacktestRuntime._publish_canonical()` passes `None` for both retention and
  deterministic-rebuild proof hashes, which unchanged Integrity blocks for a
  decision-grade request;
- current Integrity checks those proof fields for non-null presence only; it does not
  verify or recompute a durable proof body, so a facade-generated opaque hash—even
  after two same-implementation reconstructions—is insufficient acceptance evidence;
- current HEAD has no separately and independently accepted generic decision-grade
  durable rebuild/retention proof seam with an exact versioned canonical body,
  independent pre-Integrity verification/recomputation against immutable execution
  evidence, and repository replay of the same body/hash; this is an exact controllable
  H2 condition in addition to any missing applicable Profile/Build authority;
- exact `LocalMarketBundleReader.open` verifies G12D `retention-proof.json`, but this
  G12M plan neither extends that Reader nor designs the missing generic proof seam;
- `VerifiedCompletedPublicationV2` has an exact exported seven-field constructor
  frozen by architecture tests and must not be expanded; and
- Binance H3 and accepted provider artifacts remain unrelated protected history.

## Exact write set

- `../g12m-tushare-fixed-singleton-qualification-v1.md`
- this execution DAG directory
- link-only edits to `../g12m-source-bounded-qualification-v1.md`
- link/status-only edits to `../README.md`
- `docs/implementation/acceptance-matrix.md`, limited to the freeze-time G12M Tushare
  pre-decision reconciliation

No package, test, fixture, evidence, ADR, or research file. BHA-05 retained ownership
of the final H1-success or H2-blocked status/receipt update and has now written the
accepted H2 outcome under its separately authorized exact write set.

## Freeze-time exit gate (historical)

- the dependency graph was acyclic;
- every fact had one owner;
- independently owned BHA-01 was the sole eligible next node;
- BHA-02 through BHA-05 were ineligible to execute before BHA-01 decided the route;
- H2 would terminate only BHA-02 through BHA-04 and route directly to BHA-05;
- exact future write sets, independent durable-proof prerequisite, public API
  preservation, WIP, proof budget, failure precedence, fan-in, and correction rules
  were navigable;
- the Acceptance Matrix recorded the independent prerequisite gate with all code
  lanes closed, while Binance H3 remained unchanged; and
- Markdown, links, `git diff --check`, gitleaks, and independent contract review passed.

## Final outcome

BHA-01 later emitted the accepted `PREREQUISITE_INCOMPLETE` decision and is
`DECIDED_H2`. BHA-02 through BHA-04 are `TERMINATED_H2` with no outputs. BHA-05 is
`ACCEPTED_H2`, the execution DAG is `BLOCKED_H2`, and BHA-00 remains
`CONTRACT_COMPLETE` as the historical contract-freeze record.

## Freeze-time stop condition (historical)

At contract freeze, any failure to preserve independent Profile/Build authority, the
separately accepted generic durable-proof prerequisite, Resolution ownership, the
Integrity grade firewall, or one owner per Bundle/assessment fact required revising
BHA-00 before BHA-01 or code. The accepted H2 route has now closed that decision.
