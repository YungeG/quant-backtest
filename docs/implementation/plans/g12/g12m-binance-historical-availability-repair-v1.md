---
id: G12M-BINANCE-HISTORICAL-AVAILABILITY-REPAIR-V1
readiness: DRAFT_REPAIR_PLAN
status: RESEARCH_GATE_REQUIRED
owner: backtest historical availability and provider qualification
produces:
  - provider-time versus acquisition-time governance
  - additive Binance funding-history availability authority
  - causally consumable source publication or an explicit permanent blocker
  - execution-Bundle membership and Runtime consumption proof
  - causality-preserving MarketEvent-to-funding execution crosswalk
consumes:
  - ADR 0008
  - accepted Binance USD-M funding-history source-bounded v2
  - existing MarketEvent dual-time contract
  - existing SourceSnapshot acquisition-time evidence
  - existing Runtime Resolution, Timeline, Integrity, trace, and accounting authority
depends_on:
  contract: [G10E, G12A, G12C, G12D, G12L-BINANCE-USDM-FUNDING-HISTORY-SOURCE-BOUNDED-V2, G12M-SOURCE-BOUNDED-QUALIFICATION-V1]
  write_conflict: [historical-availability-governance, runtime-integrity-policy, acceptance-registry]
---

# G12M Binance historical availability repair v1

## Outcome

Repair the incorrect equivalence:

```text
MarketEvent.available_time = local acquisition/receipt time
```

for historical market data where accepted provider semantics can establish when the
exact event revision became usable by a market participant.

The repair is additive. It must not modify the accepted funding-history v2 module,
report, fixture, Event bytes, Event hashes, Bundle identity, public interfaces, or
qualification flags. The v2 report remains valid post-hoc observed-as-of evidence.

A successful repair creates a new source version only after an independent authority
gate proves a defensible provider availability time. If that authority cannot be
established for the 2024 rows, the 2024 case remains blocked and the plan switches to
prospective capture for future funding periods.

## First-principles correction

Historical backtests commonly download old market data later. Local download time is
lineage evidence; it is not automatically the time at which the market first exposed
the underlying fact.

The domain must keep four times distinct:

| Term | Meaning | Current representation |
| --- | --- | --- |
| Event Time | When the market event became effective | `MarketEvent.event_time` |
| Provider Availability Time | Earliest defensible instant the exact event revision was usable under provider semantics | `MarketEvent.available_time` |
| Acquisition Time | When this repository captured the retained bytes | `SourceSnapshotMember.acquired_at_epoch_nanoseconds` and report `observed_at` |
| Assessment Time | When G12M evaluated already-published evidence and Run identities | future provider-specific assessment field |

Rules:

1. acquisition time never silently substitutes for provider availability time;
2. event time never silently substitutes for provider availability time;
3. a provider-specific accepted authority may establish provider availability from
   target-effective publication or settlement semantics;
4. when no such authority exists, fail closed to acquisition time and retain a
   post-hoc-only claim;
5. each correction/revision has its own availability time; a later revision cannot
   rewrite what an earlier Decision Context could observe.

No global availability framework, provider registry, policy DSL, fallback chain, or
new grade system is authorized.

## Existing artifacts that remain immutable

The following remain unchanged:

- funding-history v2 implementation `024e5f209a94bb358946f5c468630108981f0329`;
- response `sha256:e9f73f9c845c28abb31037d8230df2d6f13d5d368c43436e891fcc757372c338`;
- receipt `sha256:a92989478047de7d744744aedeaf365f7d16240b536c1ccece749abe3b4efa36`;
- Snapshot `sha256:a45d9acdcfb4d42d1c70af44969f6a5151fb260c4c3040943b3d961c1073aa3f`;
- report `sha256:29e639615c1e5f5fa05ffdff9bc77a630d56838c7b0e70230177922bdbffc37b`;
- report file `sha256:850cf2b5b2f3caffd7afc1cb4f364e6224c4022417ae46bb01a406600e971951`;
- all v2 Event IDs/hashes, stream bytes, manifest, BundleRef, flags, limitations,
  tests, and public surfaces.

The repair must not reinterpret those v2 Events. Their `available_time` remains the
2026 local receipt time.

## D0 — Freeze the time vocabulary and governance

Create a new ADR rather than editing ADR 0008 in place:

```text
ADR 0009: Historical Provider Availability Is Distinct from Local Acquisition
```

The ADR must state:

- `available_time` means provider/market knowledge time, not repository download
  time;
- `observed_at` and SourceSnapshot acquisition time remain exact local evidence;
- dataset-specific provider semantics may establish availability only when exact,
  target-effective authority is retained and hashed;
- a missing authority is `UNKNOWN`, which remains fail-closed;
- current v2 artifacts retain their original meaning;
- source-bounded qualification still cannot mint or upgrade `ResultGrade`;
- future provider correction/finality uncertainty remains an explicit limitation
  under ADR 0008 and cannot silently alter prior Runs.

Add the four terms above to `CONTEXT.md` without implementation details.

### D0 acceptance

- independent governance review passes;
- no existing ADR, canonical fixture, or hash changes;
- no global policy abstraction is introduced;
- Acceptance Matrix and G12 README distinguish upstream evidence readiness from
  causal Runtime qualification.

## D1 — Establish Binance authority before writing code

Research exact first-party Binance materials effective for the target 2024 funding
period. The research must answer separately:

1. when a USD-M funding rate becomes final for settlement;
2. what `fundingTime` means;
3. whether Funding Rate History `markPrice` is the exact funding settlement mark;
4. when the exact rate + mark record becomes available to a participant;
5. whether publication delay is exact, bounded, or undocumented;
6. whether Binance documents correction/revision behavior for settled funding rows;
7. whether the current endpoint may return a value revised after the original
   settlement.

Retain raw official bytes, local receipts, SourceSnapshots, request scope, content
hashes, document effective dates, and explicit limitations. Secondary sources cannot
supply authority.

D1 has exactly three outcomes:

### H1 — Historical authority accepted

Proceed only if exact target-effective provider semantics support the exact rate +
mark revision at the funding settlement instant for each of the three 2024 rows,
without assuming that local acquisition occurred in 2024. The current G10E funding
path rejects publication after `target_funding_time`, while `MarketEvent` rejects
availability before `event_time`; for this source case H1 therefore requires:

```text
provider_available_time = funding_time = settlement instant
```

A documented post-settlement publication delay does not satisfy H1 for the existing
funding execution semantics.

### H2 — Prospective authority only

If Binance semantics are insufficient for the old rows but prospective capture can
record the necessary publication/settlement evidence, permanently retain the 2024
case as post-hoc-only and terminate this plan's D2-D8 branch. Author a separate
versioned prospective source case for future funding periods; it must use its own raw
capture, scope, Snapshot, availability authority, Events, Bundle, Run, and assessment
and must not consume the accepted 2024 v2 report as causal source input.

### H3 — No causal authority

Stop. Do not implement source v3, a joined execution Bundle, or a successful G12M
assessment. Record the unresolved authority as the final blocker.

No code lane in this plan starts before H1 is independently accepted. H2 authorizes
only a separate prospective plan; H3 authorizes no implementation.

## D2 — Freeze one closed provider-specific availability authority

After D1 reaches H1, freeze one exact provider-specific canonical value. H2 and H3
do not enter D2. Do not create a generic availability policy interface.

The value must bind at least:

- provider and dataset;
- exact instrument and funding times;
- exact authority SourceSnapshot/document identities;
- target-effective interval;
- one exact provider availability instant per retained funding row;
- the authority basis for each instant;
- correction/revision limitations;
- observed/acquired time of the authority evidence;
- direct predecessor identity when corrected;
- canonical authority hash.

Prefer a closed tuple of exact row availability facts over a formula or DSL:

```text
(funding_time, provider_available_time, authority_source_hash)
```

This exact historical funding plan does not accept a positive publication delay: the
current funding eligibility instant is the funding settlement instant. No inferred,
calibrated, caller-selected, or configurable time is allowed.

### D2 invariants

- `provider_available_time == funding_time` for every retained row;
- every retained row has exactly one availability fact;
- authority scope and funding row scope match exactly;
- authority acquisition time remains separate from provider availability;
- constructor-bypass and canonical reconstruction fail closed;
- no credential, cookie, header, environment value, raw exception, or object repr is
  serialized.

## D3 — Publish additive funding-history source v3

Create a provider-specific off-root Builder module. It should reuse the accepted v2
canonical report as its source-row and normalization authority rather than duplicate
the REST parser and decimal grammar.

The minimal interface consumes exact canonical bytes for:

1. the accepted v2 observation report; and
2. the accepted D2 availability authority.

It produces a new v3 report and new v3 Events.

Required v3 semantics:

```text
event_time     = fundingTime
available_time = accepted provider availability fact = fundingTime
phase          = market-data phase before funding eligibility
source_sequence = retained provider row order
observed_at     = retained 2026 v2 acquisition time
```

The v3 report must bind the v2 report hash, availability-authority hash, source-row
hashes, new Event hashes, stream hash, manifest, BundleRef, limitations, and direct
predecessor when one exists.

All v3 identities are new. The implementation must not copy v2 Event hashes while
changing availability. For each row, derive the first v3 `revision_id` from a closed
preimage binding at least the source-record hash and availability-authority hash.
The first v3 Event has `supersedes_revision_id = null`: v2 is an evidence predecessor
under another publication contract, not a provider revision in the v3 Event chain.
A later v3 correction for the same funding slot derives a new `revision_id` and sets
`supersedes_revision_id` to the directly preceding v3 revision only. Canonical
reconstruction and correction tests must verify both fields. If availability
authority changes, create a new report and new Event/revision identities; do not
mutate v3 history.

### D3 rejection cases

- availability authority does not cover all rows;
- funding times, instrument, provider, dataset, or source-row hashes differ;
- provider availability differs from funding time;
- authority is current-only rather than target-effective;
- caller supplies a naked hash, boolean, mapping, delay, or timestamp override;
- v2 canonical reconstruction fails;
- any output accidentally retains `available_time = observed_at` without an explicit
  post-hoc-only outcome.

## D4 — Establish production decision-grade Profile authority

Freeze the additive/versioned production Profile capability contract before building
the execution Bundle. Do not flip existing Binance Development registrations.

The profile lane must independently close or explicitly reject at least:

- funding-source eligibility;
- account/financial-event authority;
- bar execution semantics and parity;
- price-purpose coverage;
- fee and rounding authority;
- settlement behavior;
- Build/Profile/Environment compatibility.

If any required production limitation remains decision-grade blocking, G12M remains
blocked. G12M does not own this lane and cannot waive it.

This preserves the order:

```text
Profile and Integrity establish grade
G12M later binds source evidence to the already-graded Result
```

No G12M-to-grade bootstrap cycle is allowed.

## D5 — Build one complete execution Bundle

Only after D4 freezes the exact required capabilities, build the execution Bundle.
The source evidence Bundle and production execution Bundle have different identities.
Do not require their `MarketBundleRef` values to be equal.

Build one immutable execution Bundle containing:

- the exact accepted v3 funding stream;
- `account.financial-event`;
- `bar_open`;
- Binance price-purpose streams;
- the required target stream for the selected strategy family;
- every other capability required by the accepted D4 Market and Simulation Profiles.

Use existing `MarketBundleManifest` and stream manifests as the membership proof. Do
not add a second bundle catalog or a separate inclusion-proof framework.

The run Bundle manifest must contain a funding stream entry whose:

- stream key;
- capability/version;
- event count;
- stream content hash; and
- replayed ordered Event hashes

match the accepted v3 report exactly.

Coverage must include every Event Time and permit every Provider Availability Time to
be emitted at the funding instant before `request.timeline_window.end_exclusive`. It
must not extend coverage merely to make a late local receipt pass. No resampling,
forward fill, synthetic Bar, nearby mark, role fallback, or cross-Bundle read is
allowed.

## D6 — Integrate v3 Events with the existing funding execution path

Add one provider-specific, pure adapter at the Runtime-to-Kernel seam; do not add a
second funding resolver. The adapter converts an exact accepted v3 `MarketEvent` into
the existing `BinanceUsdmFundingRateRecord` consumed by G10E.

The adapter must preserve causal and source lineage:

```text
record.funding_time                 = event.event_time
record.archive_available_at        = event.timeline_instant
record.event_id                    = event.event_id
record.revision_id                 = event.revision_id
record.source_ref.source_hash      = event.event_hash
record.source_ref.supersedes_revision_id = event.supersedes_revision_id
```

The adapter must validate exact event type, capability, instrument, phase, payload,
decimal strings/units/scales, source-record hash, and funding purpose before returning
the existing record type. It accepts no mapping, fallback timestamp, nearby mark,
caller boolean, or naked hash.

For this exact path, the Event must be available in the market-data phase at the same
UTC instant as the target funding settlement, before the existing funding eligibility
phase. The existing resolver may continue to create its settlement publication at the
funding instant only because the adapter proves that the source Event was already
visible at that instant.

D6 must freeze a deterministic crosswalk from:

```text
v3 MarketEvent ID/hash
→ BinanceUsdmFundingRateRecord event/source-ref hash
→ selected funding-source resolution
→ settlement/accounting evidence
```

This crosswalk is evidence, not a new source registry or resolver. Architecture tests
must prove Runtime does not import Builder and Kernel does not import Runtime.

## D7 — Produce and verify one canonical Run

Execute one persisted Run using the complete D5 Bundle, accepted D4 Profiles, and D6
adapter. Freeze:

- request and semantic Run identity;
- Bundle, Build, Profile, and Environment identities;
- requested and result grade;
- Integrity context/report;
- execution result and completed publication;
- timeline trace;
- D6 adapter crosswalk;
- accounting trace/journal.

The canonical trace must contain every required funding Event ID/hash at the exact
funding/Provider Availability Time, and the D6 crosswalk must prove that the same
Event reached the selected funding-source resolution.

Accounting proof is a disposition proof, not a requirement to manufacture money
movement:

- when a relevant position exists, verify exact funding settlement and journal
  identities;
- when no relevant position exists, verify an explicit zero-exposure or
  `NOT_APPLICABLE` disposition.

At least one acceptance journey should hold a relevant position across a funding
Event so the financial path is exercised. A separate zero-position test must prove
that absence of a journal mutation does not imply absence of Event consumption.

## D8 — Implement the read-only provider-specific G12M assessment

Only after D1-D7 pass, freeze a small Runtime interface for this exact source case.
The module must be provider-specific, off-root, pure, and read-only.

It consumes exact canonical bytes for the accepted v3 source report, availability
authority, completed publication, execution-Bundle manifest, exact funding-stream
payload, D6 adapter crosswalk, and any receipt bytes required by the frozen contract.
It performs no filesystem, network, repository, Reader, Builder, or provider-client
I/O and imports no Builder package.

It must independently bind:

- provider, dataset, scope, instrument, and funding times;
- v2 source evidence and v3 availability authority;
- source stream membership in the execution Bundle by reconstructing the manifest
  and funding-stream payload, then verifying BundleRef, stream declaration, event
  count, stream content hash, and ordered v3 Event hashes;
- exact Run/Integrity/publication identities;
- requested/result grade copied from the existing Integrity report;
- timeline Event consumption and D6 adapter crosswalk;
- accounting dispositions;
- assessment time and direct supersession.

A Development Result produces a canonical non-qualified assessment. The assessor
never mints, upgrades, or downgrades grade.

Failure precedence must distinguish malformed bytes, invalid authority, source-row
mismatch, Bundle membership mismatch, causal availability mismatch, adapter-crosswalk
mismatch, missing trace, invalid accounting disposition, invalid Run identity, and
invalid direct supersession. Failure artifacts contain identifiers only, never raw
bytes or exception text.

## D9 — Acceptance and governance fan-in

After independent review and validation:

1. mark the exact v3 source lane accepted or permanently blocked;
2. update the G12 README and Acceptance Matrix;
3. supersede the stale Binance `nominal ready` wording;
4. link the v2 post-hoc report, D2 availability authority, v3 source report,
   execution Bundle, adapter crosswalk, canonical Result, and G12M assessment
   identities;
5. keep historical v2 artifacts and prior blocker documents discoverable;
6. leave legal, live, deployment, provider-finality, and provider-global-completeness
   claims false or explicitly limited.

## Validation matrix

| Gate | Minimum runnable proof |
| --- | --- |
| D0 governance | ADR/context/registry review; protected-byte diff check |
| D1 authority | raw-source replay, exact-scope hashes, independent primary-source review |
| D2 availability | canonical golden reconstruction plus malformed/scope/time adversarial cases |
| D3 source v3 | exact v2 replay, authority binding, Event/stream/manifest golden, correction test |
| D4 Profile | production grade resolution and all blocking limitations fail closed |
| D5 execution Bundle | required-capability resolution, stream membership, one-Bundle and no-resampling architecture tests |
| D6 execution adapter | Event-to-record golden crosswalk, exact timing/phase, malformed payload, and import-boundary tests |
| D7 Run | persisted replay, Integrity verification, funding trace/crosswalk, position and zero-position disposition tests |
| D8 G12M | success/non-qualified/failure/supersession golden tests and Runtime→Builder architecture test |
| D9 fan-in | focused, adjacent, architecture, full repository, Ruff/LSP, diff, and secret scan |

## Delivery order and write ownership

Use independent worktrees and one writer per lane:

```text
D0 governance
  ↓
D1 authority research
  ├─ H1 → D2 availability authority
  │         ↓
  │       D3 source v3 ───────────────┐
  │         ↓                         │
  │       D4 production Profiles      │
  │         ↓                         │
  │       D5 execution Bundle         │
  │         ↓                         │
  │       D6 execution adapter        │
  │         ↓                         │
  │       D7 canonical Run            │
  │         ↓                         │
  │       D8 G12M assessment          │
  │         └───────────────→ D9 governance fan-in
  ├─ H2 → stop 2024 branch; author separate prospective plan
  └─ H3 → permanent blocker
```

Acceptance Matrix, G12 README, main branch, and final commits remain single-writer.
No lane may modify accepted v1/v2 bytes, fixtures, hashes, IDs, or public interfaces.

## Stop conditions

Stop rather than weaken the model when:

- no target-effective Binance authority establishes historical rate + mark
  availability;
- the authority proves only that a record existed but not when the exact revision was
  usable;
- a complete execution Bundle cannot preserve exact stream membership;
- decision-grade Profile authority cannot be established independently;
- the canonical Run lacks Event trace or deterministic accounting disposition;
- the only proposed repair is backdating, extending coverage to receipt time,
  substituting data, self-attested grade, or synthetic Result construction.

## Final acceptance statement

This repair succeeds only when it proves all three statements separately:

```text
The exact market fact was effective at Event Time.
The exact retained revision was defensibly usable at Provider Availability Time.
This repository acquired and preserved its bytes at Acquisition Time.
```

Only the second statement controls causal Runtime visibility. The third statement
controls evidence lineage and must never silently replace the second.
