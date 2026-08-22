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

This docs-only plan commit completes BHA-00. The independently owned BHA-01
Profile/Resolution/Build authority lane is the immediate Ready node.

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
- `docs/implementation/acceptance-matrix.md`, limited to the current G12M Tushare
  research-gate/code-not-ready reconciliation

No package, test, fixture, evidence, ADR, or research file. BHA-05 still owns the
later final H1-success or H2-blocked status/receipt update.

## Exit gate

- dependency graph is acyclic;
- every fact has one owner;
- independently owned BHA-01 is the only next node;
- BHA-02 through BHA-05 are explicitly not Ready;
- H2 terminates only BHA-02 through BHA-04 and routes directly to BHA-05;
- exact future write sets, independent durable-proof prerequisite, public API
  preservation, WIP, proof budget, failure precedence, fan-in, and correction rules
  are navigable;
- the Acceptance Matrix now agrees that Tushare is at the independent research gate
  with no code lane Ready, while Binance H3 remains unchanged; and
- Markdown, links, `git diff --check`, gitleaks, and independent contract review pass.

## Stop condition

If review cannot preserve independent Profile/Build authority, the separately accepted
generic durable-proof prerequisite, Resolution ownership, the Integrity grade
firewall, or one owner per Bundle/assessment fact, revise BHA-00
only. Do not start BHA-01 or code.
