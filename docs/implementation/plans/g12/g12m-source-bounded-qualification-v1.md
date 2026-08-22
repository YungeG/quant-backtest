---
id: G12M-SOURCE-BOUNDED-QUALIFICATION-V1
readiness: A_SHARE_RESEARCH_GATE_CODE_NOT_READY_BINANCE_H3_PERMANENT_BLOCK
gate_status: DRAFT
owner: backtest-runtime qualification
produces:
  - future provider-bounded G12M implementation contract
consumes:
  - ADR 0008
  - accepted G12I SZSE evidence slice
  - accepted G12K Tushare fixed-instrument evidence slice
  - accepted Binance FAPI funding-history observed-as-of evidence slice
depends_on:
  contract: [G07, G12I, G12K, G12L-*]
  evidence:
    - exact canonical upstream artifacts and accepted hashes required by each provider-specific case
    - independently accepted applicable Profile/Build authority required by the Tushare case
    - independently accepted generic durable rebuild/retention proof prerequisite required by the Tushare case
  write_conflict: [runtime-integrity-policy, acceptance-registry]
---

# G12M source-bounded qualification readiness

## Outcome

Prepare a future Runtime-owned, read-only qualification of an already graded
backtest result under [ADR 0008](../../../adr/0008-source-bounded-decision-grade.md).
One exact Tushare-only A-share case has accepted G12I and fixed-singleton G12K
canonical artifacts, and one exact Binance funding-history case has an accepted
observed-as-of canonical report. This governance plan does not itself authorize a
production Runtime interface. The authoritative remaining Tushare decomposition is
[G12M Tushare fixed-singleton qualification v1](g12m-tushare-fixed-singleton-qualification-v1.md);
it permits H1 only after independently accepted applicable Profile/Build authority
and a separately independently accepted generic durable rebuild/retention proof
prerequisite exist before any code lane. BHA-01 only binds those immutable prerequisite
identities. Resolution remains runtime compatibility authority and Integrity remains
sole grade authority. Binance remains closed by its accepted H3 decision.

## Status

`DRAFT / TUSHARE INDEPENDENT RESEARCH GATE; CODE NOT READY; BINANCE H3
PERMANENTLY BLOCKED`. ADR 0008 policy is unchanged. Accepted Tushare G12I/G12K
artifacts are provider evidence only; BHA-01 is the sole Ready research node and no
code lane is Ready. Current HEAD lacks the accepted generic durable proof seam, which
is an exact controllable H2 condition independent of any missing applicable
Profile/Build authority.
The Binance funding-history v2 report remains accepted as exact post-hoc upstream
evidence, with `available_time` fixed at the 2026 receipt instant. Accepted H3
`NO_CAUSAL_AUTHORITY` permanently terminates the historical BHA-03 through BHA-09
branch. No Binance source v3, Profile input, Bundle, adapter, Run, assessment, or
prospective plan exists or is authorized. General/dynamic-universe G12K and other
provider combinations remain blocked on their own missing lanes.

No production code, generic G07 proof implementation, public type, function signature,
serialized assessment body, failure enum, test contract, or write set is authorized
by this common plan; the provider-specific Tushare plan owns only the gated
provider-specific future write sets. Tushare research-gate
status is independent of the Binance H3 decision.

## Decision frozen now

ADR 0008 is the only frozen decision:

- Tushare and Binance remain the sole market-data providers;
- source-bounded decision grade is allowed when all controllable evidence passes;
- impossible provider assurances remain explicit limitations rather than ordinary
  historical-backtest blockers;
- existing `RequestedResultGrade`, `ResultGrade`, v1 artifacts, canonical bytes,
  hashes, flags, and APIs remain unchanged;
- G12M never mints, derives, upgrades, or downgrades run grade;
- correction handling is append-only: provider-specific successor edges, new semantic
  Run identity, and a new assessment, with old runs/results immutable and auditable;
  and
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

| Lane | Provider-specific readiness | Acceptance identity |
| --- | --- | --- |
| G12I SZSE | `ACCEPTED`: exact July-2026 Tushare `daily`/`trade_cal`/`suspend_d` observation report, canonical replay, append-only correction identity, and nominal Runtime boundary below. | Source `4389877b8879fc9bb1a6d6544c4079a7d29312ab`; report `sha256:ff09c4ad9f8025e66689387b5132d3d85c4101276fbf7330dd5040af111cc029`; canonical file `sha256:9cbfc115e41f56d1e83eac520856c3f529f83972b97111238e5dbb1a68c4eae6`. |
| G12K Tushare fixed singleton | `ACCEPTED`: exact full `dividend(ts_code="000001.SZ")` response, receipt/Snapshot replay, fixed July-2026 scope, 96 ordered source rows, zero target-relevant rows, append-only direct-predecessor evidence, and explicit limits. This is not listing/universe/survivorship/lifecycle authority. | Source `28a4d7234f5101e67bfa64f1eded92b81bfcf73d`; report `sha256:5a49065d87286a9673893337328ddbbab9a19cd3addf178bf96033b9b1babfd7`; canonical file `sha256:a386f4281374d1449c0b5ba4371b9e9d2de5b236bc8fc5b5cdd8de5e43c65956`; final plan `sha256:79402fe89df8bffc23be4ff2772bbba14510f6a6133de8fe48acca1b0656c5d8`. |
| Binance FAPI funding history | `UPSTREAM V2 EVIDENCE ACCEPTED / H3 PERMANENTLY BLOCKED`: exact v2 post-hoc evidence remains accepted, but H3 `NO_CAUSAL_AUTHORITY` terminates historical BHA-03 through BHA-09. No causal Runtime or prospective route is authorized. | Source `024e5f209a94bb358946f5c468630108981f0329`; v2 Snapshot `sha256:a45d9acdcfb4d42d1c70af44969f6a5151fb260c4c3040943b3d961c1073aa3f`; v2 report `sha256:29e639615c1e5f5fa05ffdff9bc77a630d56838c7b0e70230177922bdbffc37b`; H3 decision JSON `sha256:a0f8fff9ed75db74abb9fd596ad6b3c79bd1a1c75e823e5bef5b5c63e0b2a3e2`; decision report `sha256:130bfc81c8c97e47992a90354c64b28bebee8053fafc48eb63eb07c942f407af`; manifest file `sha256:760d44f9a4b1627f7f2a176336ba74a2924f7eecaf44ac7ba72e78d93f99e6f6`; accepted main `600259a9f22e44102e5e60faab3176cbf5761e6e`. |

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

## Frozen G12K fixed-singleton nominal reconstruction boundary

A future Tushare-only A-share G12M implementation must independently consume the
accepted G12K evidence as exact canonical bytes for type
`g12k_fixed_instrument_source_bounded_observation_report`, schema version `1`. It
must use a closed nominal Runtime value that mirrors every accepted field; it must
not import Builder or accept an open mapping, generic `ArtifactRef`, caller boolean,
class-name assertion, or naked hash.

Reconstruction must reject noncanonical JSON, duplicate/extra/missing keys,
constructor bypass, nested substitution, any true qualification flag, hashes or
relevance inconsistent with retained source-row replay, and any mismatch in the
fixed provider, dataset, instrument, XSHE/SZSE scope, accepted catalog/G12I
identities, member/hash/time bindings, limitations, or null first-capture
`supersedes_report_hash`. It must bind these accepted identities:

- implementation source `28a4d7234f5101e67bfa64f1eded92b81bfcf73d`;
- canonical report file `sha256:a386f4281374d1449c0b5ba4371b9e9d2de5b236bc8fc5b5cdd8de5e43c65956`;
- report `sha256:5a49065d87286a9673893337328ddbbab9a19cd3addf178bf96033b9b1babfd7`;
- receipt `sha256:5524257ee9a464d8e72df803c1493bc92e59420f0af1f6593b23a22dbb93a240`;
- snapshot `sha256:ecb17991e82a73cc2eaaaa457ff72ccd89cb1a4a23fd595419983028f2c4a5c4`;
- content tree `sha256:734b7b3460fda376ee105619fc4f20da33f88a3e5693de50c92389782b872809`;
- provenance `sha256:475f9a488e7e8c761bd01f55528f1185a1aacbba4868c00190d51a1200c18e0d`;
- request scope `sha256:5738442bf477fc2f60542fa4b0ddee7be8d737d068077eefaa63d72489935ed7`;
- catalog canonical file `sha256:d71ca8ed8977bf5fa0aa7cd1ab11fb85abcd5382f42c7e2bb2243d5b5290e456`;
- instrument catalog `sha256:99df0de0dc3008cf557bb7634caf483fae27488c75016421218100df6a77a6cc`;
- retained rows `sha256:2ed79936a664545591c2f3baf7224c7a632f17416c120eae22022eac56ed07aa`;
- ordered row-hash tuple `sha256:774f8cb53478581c3137c6cc086a76552a0719cfaa121df790c451368b37fb84`;
- empty relevant-row tuple `sha256:4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`;
- final upstream plan `sha256:79402fe89df8bffc23be4ff2772bbba14510f6a6133de8fe48acca1b0656c5d8`.

The Runtime boundary must cross-check the embedded G12I report/canonical-file
identities against the independently reconstructed accepted G12I value, require the
19 ordered daily dates/Event hashes to match exactly, and require G12K
`observed_at` not earlier than G12I `observed_at`. It must separately prove the
bound run uses exactly singleton `xshe:000001`, has no dynamic universe selector,
and that the assessment instant is not earlier than G12K `observed_at`.

The 19 daily rows mean only `OBSERVED_DAILY_ROW_AT_SESSION`; the zero selected
dividend rows mean only
`NO_TARGET_RELEVANT_ROW_RETURNED_AT_OBSERVED_AS_OF`. Neither is listing membership,
whole-universe completeness, survivorship safety, action absence, lifecycle
closure, or provider finality. A corrected G12K capture is a new accepted canonical
report whose direct predecessor was evidence-replayed; it cannot silently replace
these identities.

## Accepted Binance funding-history post-hoc evidence boundary

The accepted v2 report remains discoverable as exact post-hoc upstream evidence only:

- implementation source `024e5f209a94bb358946f5c468630108981f0329`;
- response/member `sha256:e9f73f9c845c28abb31037d8230df2d6f13d5d368c43436e891fcc757372c338`;
- receipt `sha256:a92989478047de7d744744aedeaf365f7d16240b536c1ccece749abe3b4efa36`;
- Snapshot `sha256:a45d9acdcfb4d42d1c70af44969f6a5151fb260c4c3040943b3d961c1073aa3f`;
- Event tuple `sha256:9ca70dd34ce79e0f3505f2bb40cace8299557d9b9b67895c5d4a9588262677de`;
- manifest content `sha256:1a4e5db873e59e1c761531a926857c424d51494d02ba06c6f76ffc851e7e47f1`;
- Bundle-ref manifest `sha256:352aa6a20c9c04dc998d07e6935f6bb635fb52459a361648262565d5773423fb`;
- report `sha256:29e639615c1e5f5fa05ffdff9bc77a630d56838c7b0e70230177922bdbffc37b`;
- canonical report file `sha256:850cf2b5b2f3caffd7afc1cb4f364e6224c4022417ae46bb01a406600e971951`;
- final upstream plan `sha256:8a5d5643db1baa6bd50d26e6ab4220df948ca3122a46214a710dd47cd9299686`.

Accepted H3 authority is linked by the
[decision report](../../../research/g12m-binance-funding-availability-authority-decision-v1.md),
[canonical decision](../../../../evidence/g12m-binance-funding-availability-authority-decision-v1/decision.json),
and [manifest](../../../../evidence/g12m-binance-funding-availability-authority-decision-v1/manifest.sha256).
Their hashes are respectively
`sha256:130bfc81c8c97e47992a90354c64b28bebee8053fafc48eb63eb07c942f407af`,
`sha256:a0f8fff9ed75db74abb9fd596ad6b3c79bd1a1c75e823e5bef5b5c63e0b2a3e2`,
and `sha256:760d44f9a4b1627f7f2a176336ba74a2924f7eecaf44ac7ba72e78d93f99e6f6`.

No Binance Runtime reconstruction contract is authorized. Historical BHA-03 through
BHA-09 are permanently `TERMINATED_H3`; no source v3, Profile input, Bundle, adapter,
Run, or assessment exists. The accepted v2 report cannot be reused as causal input,
and no prospective plan is authorized. Immutable 2024 publication availability,
permanent provider identity/finality, complete correction lineage, provider-global
completeness, legal closure, live eligibility, and deployment authorization remain
false or limited.

## Readiness exit criteria

A provider-specific G12M contract may freeze only after every upstream lane required
by that exact case provides:

1. exact provider, dataset, finite scope, source authority, and observed-as-of
   semantics;
2. canonical artifacts whose accepted hashes bind the retained provider evidence
   and the relevant normalized/published scope;
3. a verifier or nominal value boundary that Runtime can consume without
   importing Builder or performing I/O;
4. explicit limitation semantics for unavailable permanent identity, revision
   finality, provider scope completeness, and any applicable joined Binance funding
   evidence;
5. append-only correction identity sufficient to distinguish a new snapshot from
   the superseded evidence; and
6. accepted tests, architecture checks, immutable commit identities, and review
   closure owned by each upstream lane.

The accepted G12I and fixed-singleton G12K lanes satisfy the upstream provider-evidence
criteria for the exact Tushare-only A-share case; they do not satisfy the independently
accepted applicable Profile/Build prerequisite, the independently accepted generic
durable rebuild/retention proof prerequisite, or Runtime market-data contracts.
The remaining Tushare route and its honest code start gate are owned by
[G12M-TUSHARE-FIXED-SINGLETON-QUALIFICATION-V1](g12m-tushare-fixed-singleton-qualification-v1.md).
The accepted Binance funding-history v2 lane supplies exact post-hoc upstream evidence only. H3
`NO_CAUSAL_AUTHORITY` permanently closes the historical causal route: no closed
nominal value, run/Integrity binding,
assessment artifact, failure contract, test, or write set is authorized for the
terminated BHA-03 through BHA-09 branch. Neither provider case depends on the other.

Any new G12M contract must bind the accepted finite artifacts directly; it must not
introduce a provider registry, generic source framework, facts registry, or policy
DSL.

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
source framework, facts registry, policy DSL, Binance prospective plan, legal
certification, live trading, deployment authorization, permanent provider finality,
or provider-global completeness claim is approved.
