---
id: G12M-BINANCE-USDM-FUNDING-HISTORY-QUALIFICATION-V1
readiness: BLOCKED
status: D1_BLOCKER_ANALYSIS
owner: backtest-runtime qualification
produces:
  - provider-specific Binance qualification blocker closure
consumes:
  - ADR 0008
  - G12M source-bounded qualification governance v1
  - accepted Binance USD-M funding-history source-bounded v2 report
  - existing Runtime Integrity and timeline authority
depends_on:
  contract: [G07, G10E, G12A, G12C, G12D, G12L-BINANCE-USDM-FUNDING-HISTORY-SOURCE-BOUNDED-V2]
  write_conflict: [runtime-integrity-policy, acceptance-registry]
---

# G12M Binance USD-M funding-history qualification v1

## Outcome

Do not implement a successful Binance G12M qualification yet.

The accepted source-bounded v2 report is sufficient for exact post-hoc source
reconstruction, but it cannot satisfy ADR 0008's causal run-binding requirement:
all three Events are available only at the 2026 local receipt instant while their
bundle coverage ends on 2024-01-02. Runtime therefore cannot consume those Events
inside any request window valid for that Bundle.

Current production Binance profiles are also development-only, and no accepted
Binance decision-grade canonical Result exists. A synthetic decision-grade fixture
would be self-attestation, not qualification.

This D1 closes the provider-specific design question as `BLOCKED`. It authorizes no
Runtime module, public type, function, assessment fixture, grade change, live claim,
or deployment claim.

## Accepted source boundary

The frozen source case remains accepted exactly as evidence, not as causal Runtime
qualification:

- provider `binance.fapi`, dataset `fundingRate`;
- instrument `binance_usdm:btc-usdt-perpetual` / symbol `BTCUSDT`;
- request `1704067200000..1704153599999`, `limit=100`;
- three provider-order rows at `00:00`, `08:00`, and `16:00` UTC with exact funding
  rate and funding-time mark;
- coverage `[1704067200000000000, 1704153600000000000)` epoch nanoseconds;
- local observed/available time `1787304863983843230` epoch nanoseconds;
- first capture only (`supersedes_report_hash = null`).

Accepted identities remain immutable:

- upstream implementation `024e5f209a94bb358946f5c468630108981f0329`;
- canonical report file `sha256:850cf2b5b2f3caffd7afc1cb4f364e6224c4022417ae46bb01a406600e971951`;
- report `sha256:29e639615c1e5f5fa05ffdff9bc77a630d56838c7b0e70230177922bdbffc37b`;
- response/member `sha256:e9f73f9c845c28abb31037d8230df2d6f13d5d368c43436e891fcc757372c338`;
- receipt `sha256:a92989478047de7d744744aedeaf365f7d16240b536c1ccece749abe3b4efa36`;
- request scope `sha256:e749c6265a08ebc7095c96c3636e3070eceb3f5cd82e2e981d9d23167ef50be1`;
- snapshot `sha256:a45d9acdcfb4d42d1c70af44969f6a5151fb260c4c3040943b3d961c1073aa3f`;
- content tree `sha256:b992587527ddb79b5d752a0bc060cad8bdfd960b874f194d49f16033f171dfd0`;
- provenance `sha256:8591a52c953f11179a3ddc59e9c16db7d28518d7220643f73b31967683e760f6`;
- source rows `sha256:39883ccd15ba2aaa6dc5235214331eb0abc0ecacc6851aec007391415e2086f8`;
- ordered source-record hashes `sha256:a580b16bdcd1093a2125a63d336649133400a930b6a44af9e592f2c22ddce2b2`;
- ordered Event hashes `sha256:9ca70dd34ce79e0f3505f2bb40cace8299557d9b9b67895c5d4a9588262677de`;
- stream `sha256:edac3e0e501190a063fbd11ba33da0a3a4cae576fed3434697a2f7a0824c25d7`;
- manifest content `sha256:1a4e5db873e59e1c761531a926857c424d51494d02ba06c6f76ffc851e7e47f1`;
- Bundle-ref manifest `sha256:352aa6a20c9c04dc998d07e6935f6bb635fb52459a361648262565d5773423fb`;
- upstream plan `sha256:8a5d5643db1baa6bd50d26e6ab4220df948ca3122a46214a710dd47cd9299686`.

## Blocking proof

### B1 — observed-as-of is after every possible valid Run window

The accepted report publishes every Event with:

```text
available_time = 1787304863983843230
```

The accepted Bundle has:

```text
coverage_end_exclusive = 1704153600000000000
```

Runtime resolution requires the request timeline to remain within Bundle coverage.
Runtime timeline iteration excludes an Event when
`event.available_time >= request.timeline_window.end_exclusive`.

Because the accepted availability time is later than the Bundle coverage end, no
valid request using this Bundle can consume any of the three Events. Bundle-ref
equality would prove only that a run named the Bundle, not that it causally used the
funding evidence. ADR 0008 explicitly retains observed-as-of after evidence use and
lookahead as blockers.

Changing the assessment instant does not repair this: post-run assessment time is
not Event availability during execution.

### B2 — no production Binance decision-grade Result authority exists

Current Binance Runtime registrations and funding-source resolutions remain
`RequestedResultGrade.DEVELOPMENT` and `decision_grade_eligible = false`. There is
no accepted production Binance `FinalizedCanonicalResultV2` whose Integrity report
already binds both:

- `RequestedResultGrade.DECISION_GRADE`; and
- `ResultGrade.DECISION_GRADE`.

G12M cannot change those values. Test-only `dataclasses.replace` profiles or manually
constructed in-memory finalized graphs are not accepted provider authority.

### B3 — no immutable accepted run identity exists to freeze

ADR 0008 requires the exact verified completed publication identity, semantic run,
Integrity context/report, request, Bundle, Build, Profile, Environment, execution,
and trace bindings. No such accepted Binance decision-grade publication exists for
this source case, so no successful golden assessment identity can be frozen.

A publicly constructible in-memory `FinalizedCanonicalResultV2` proves internal
consistency only. It is insufficient by itself for this provider-specific acceptance
without an accepted persisted publication and immutable run identities.

### B4 — source receipt/currentness boundaries remain external

The accepted report binds the frozen receipt hash, but Runtime cannot replay receipt
bytes if a future seam accepts only report bytes. Any later successful contract must
either accept exact canonical receipt bytes or state the explicit limitation
`acquisition_receipt_replay_not_performed_by_runtime` while relying on upstream
acceptance.

This first-capture report also does not prove repository-head currentness after a
future correction. Any later assessment must state
`accepted_source_currentness_not_evaluated`; consumer/repository policy owns current
selection.

## Rejected shortcuts

The following do not unblock qualification:

- extending the request end into 2026, because resolution requires it within the
  accepted 2024 Bundle coverage;
- setting `assessed_at` after receipt, because assessment time is not Event
  availability;
- requiring only Bundle-ref equality, because that does not prove Event consumption;
- constructing a synthetic decision-grade profile/result in tests;
- trusting a naked report/receipt/run hash or caller boolean;
- manufacturing a historical availability time from `fundingTime`;
- substituting the monthly rate-only archive, a nearby mark-price stream, or a
  manufactured mark;
- adding a generic provider/qualification registry.

## Exact unblock requirements

A new D1 may freeze a successful interface only after all of the following are
accepted independently:

1. **Causal source availability** — exact provider evidence and publication semantics
   support `available_time` no later than each funding Event's actual Runtime use,
   without inference from event time or local wishful backdating.
2. **Compatible accepted Bundle** — one immutable Bundle contains the exact funding
   Events and all other required Binance capabilities, with a coverage window that
   permits their causal emission.
3. **Production decision-grade profiles** — accepted Binance Market/Simulation/
   Execution-account registrations are decision-grade eligible without altering
   current development artifacts.
4. **Accepted canonical Result** — one persisted and independently verified
   `FinalizedCanonicalResultV2` freezes publication, requested/result grade, semantic
   run, Integrity context/report, request, Bundle, Build, Profile, Environment,
   execution, timeline trace, and accounting identities.
5. **Consumption proof** — canonical `TIMELINE_EVENT` trace entries bind all three
   Event IDs/hashes, and funding settlement/accounting evidence proves the required
   events were applied rather than merely named by the request.
6. **Runtime source seam** — exact report and, if required, receipt bytes can be
   reconstructed without Runtime→Builder, filesystem, network, provider client,
   mapping, generic `ArtifactRef`, caller boolean, or naked hash.
7. **Correction versioning** — a corrected source requires a new provider-specific
   qualification/schema version binding the new Snapshot, direct predecessor report,
   and directly superseded assessment when one exists; otherwise the assessment
   predecessor is null. This v1 boundary never changes identity.

## Future assessment semantics

If the blockers are later cleared, a successful assessment must copy and bind the
existing requested and result grades plus Integrity context hash. It must not mint or
upgrade grade. A development result produces a canonical non-qualified assessment,
not a G12M failure.

Any future structured failure contract must separately cover malformed source bytes,
invalid canonical Result, invalid assessment instant, source/run mismatch, causal
availability/trace mismatch, and invalid direct supersession. Failure artifacts must
contain no raw bytes, exception text, credentials, environment values, or object
representations.

## Current nonclaims

The accepted funding-history v2 report supports post-hoc corroboration only. It does
not currently support `SOURCE_BOUNDED_DECISION_GRADE` for a Binance Run and does not
prove immutable 2024 publication, permanent provider identity, future finality,
complete correction lineage, provider completeness, instrument-catalog authority,
profile qualification, legal closure, live eligibility, or deployment authorization.

## Delivery status

- D1: blocker analysis frozen after independent review.
- D2 source reconstruction: not authorized while no successful qualification can
  consume it.
- D3 run binding/assessment: blocked by B1-B3.
- D4 acceptance: not applicable until a future unblocked contract is implemented and
  independently reviewed.

## Exact write set

This D1 may modify only:

- `docs/implementation/plans/g12/g12m-binance-usdm-funding-history-qualification-v1.md`.

No production code, test, fixture, existing governance file, accepted upstream
artifact, root export, or acquisition file is in scope.
