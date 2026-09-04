---
id: G12M-TUSHARE-FIXED-SINGLETON-QUALIFICATION-V2
status: CONTRACT_FROZEN / ROUTE_ACCEPTED_H1
owner: additive Tushare fixed-singleton qualification successor
status_authority: ../../acceptance-matrix.md
predecessor_route: g12m-tushare-fixed-singleton-qualification-v1.md
---

# G12M Tushare fixed-singleton qualification v2

## Outcome

Run one additive successor qualification for exact `xshe:000001`, July 2026,
zero target, zero initial/final exposure, and no trade activity. The route consumes
the accepted durable-proof seam and runnable Profile/Build authority v2; it does not
modify or reinterpret the historical v1 H2 decision, terminated nodes, receipt, or
provider evidence.

The only accepted execution entry remains:

```text
BacktestRuntime.run(request)
  -> schema-3 exact one-Bundle hydration/PREP/Resolution
  -> accepted durable proof recomputation before Integrity
  -> canonical-v3 completed publication ref V2
  -> BacktestEvidenceRepository.load_completed_v3
  -> analysis v2 derivation/repository replay
  -> pure provider-specific assessment v2
```

No direct Engine run, second facade, fabricated completed graph, caller proof, naked
hash, mapping, same-implementation double run, or assessor-created grade is legal.

## Immutable predecessor and accepted inputs

| Input | Exact identity |
| --- | --- |
| Historical BHA-01 H2 semantic predecessor | `sha256:a7a6fff66a34f20031178d82fd7da424799ecbc2b3e2c887bdd149e98cc826bb` |
| Historical BHA-01 accepted commit | `a786d9772f3732678851476ac9c51e3f10abb69b` |
| Historical v1 H2 governance | `3ad3c42a971988db6712aff507ec630c90c0ea1e` |
| G07 contract / deterministic golden | `sha256:30a2f6127969a58c946e8fde6369515aa236f7bac89c4e039ea35e7fce4f8be7` / `sha256:33f262070a59ce52a350b99dcffdd9548a0643755690beeda9afffbada20aad7` |
| G07 Backtest / Platform acceptance | `606b7e866673f3a5eb71a69196687dd653561b42` / `5948dd62f50d197f3e35d499a8e44e04b2257981` |
| Runnable Profile/Build candidate / governance | `4e2da5b4cee8addf1a5caf2b9be9f1d037a2af3b` / `773d161847e338b5f9f4baa4072c9a33e57ed534` |
| Runnable authority / Build | `sha256:3d19c05e552aa61a7f1ff33bc2451d2d0cc13e0d3ee30acde46462bdfa65becf` / `sha256:26048a80c045b8c49ab4f09936ab6ea3ef31acd767d54365caa20c8e457f7f45` |
| Exact target stream | `sha256:8e4bdddbd91e1bafd65363e133d382673df88e4dc4061d1f0dd776a42afc6cee` |
| G12I report / canonical file | `sha256:ff09c4ad9f8025e66689387b5132d3d85c4101276fbf7330dd5040af111cc029` / `sha256:9cbfc115e41f56d1e83eac520856c3f529f83972b97111238e5dbb1a68c4eae6` |
| G12K report / canonical file | `sha256:5a49065d87286a9673893337328ddbbab9a19cd3addf178bf96033b9b1babfd7` / `sha256:a386f4281374d1449c0b5ba4371b9e9d2de5b236bc8fc5b5cdd8de5e43c65956` |

G12I local Acquisition/Assessment Time is `1787292861381694496`; the target
decision/event is `1787292861381694497`. Historical Provider Availability Time
remains unknown. G12K Assessment Time is `1787299622295499670`, after the target;
G12K is Profile/assessment evidence only and never target or execution-Timeline
source evidence. Final assessment must not precede G12K Assessment Time.

## Execution DAG

```text
V2-00 contract freeze
  -> V2-01 successor prerequisite decision
       -> V2-02 exact causal execution Bundle
            -> V2-03 sole-facade canonical-v3 Run and verified evidence
                 -> V2-04 pure source-to-Run assessment
V2-01 H1 + V2-02 + V2-03 + V2-04 -> V2-05 success governance fan-in
V2-01 H2 ----------------------------> V2-05 blocked governance fan-in
```

| Node | Outcome | Contract/evidence inputs | Exact write set |
| --- | --- | --- | --- |
| V2-00 | this frozen successor contract | historical v1 H2, accepted G07, authority v2 | `docs/implementation/plans/g12/g12m-tushare-fixed-singleton-qualification-v2.md` |
| V2-01 | immutable H1 successor prerequisite decision or H2 | old H2 semantic predecessor plus all accepted identities above | `docs/research/g12m-tushare-fixed-singleton-successor-prerequisite-authority-v2.md`; `evidence/g12m-tushare-fixed-singleton-successor-prerequisite-authority-v2/decision.json`; `evidence/g12m-tushare-fixed-singleton-successor-prerequisite-authority-v2/manifest.sha256` |
| V2-02 | one G12C/D-published Local Reader execution Bundle | V2-01 H1, exact accepted G12I Events, exact accepted target, authority-v2 capabilities | `packages/market-bundle-builder/src/crypto_quant_bundle_builder/g12m_tushare_fixed_singleton_execution_bundle_v2.py`; `tests/bundle_builder/providers/tushare/test_g12m_tushare_fixed_singleton_execution_bundle_v2.py`; `tests/architecture/test_g12m_tushare_fixed_singleton_builder_v2_boundary.py`; `tests/fixtures/market_data/providers/tushare/g12m-fixed-singleton-execution-bundle-v2/` |
| V2-03 | one canonical-v3 completed Run, proof replay, analysis v2, exact verified evidence projection | V2-01 H1, V2-02, accepted authority/proof | `packages/backtest-runtime/src/crypto_quant_backtest/verified_publications.py`; `packages/backtest-runtime/src/crypto_quant_backtest/evidence_repository.py`; `packages/backtest-runtime/src/crypto_quant_backtest/g12m_tushare_fixed_singleton_route_v2.py`; `tests/runtime/g12m/test_tushare_fixed_singleton_route_v2.py`; `tests/runtime/evidence_repository/test_verified_completed_evidence_v3.py`; `tests/architecture/test_g12m_tushare_fixed_singleton_route_v2_boundary.py`; `tests/fixtures/runtime/g12m-tushare-fixed-singleton-production-run-v2/` |
| V2-04 | pure additive schema-2 source-to-Run assessment | V2-01 H1 decision, exact G12I/G12K bytes, V2-02 Bundle, V2-03 verified evidence/analysis | `packages/backtest-runtime/src/crypto_quant_backtest/g12m_tushare_fixed_singleton_assessment_v2.py`; `tests/runtime/g12m/test_tushare_fixed_singleton_assessment_v2.py`; `tests/architecture/test_g12m_tushare_fixed_singleton_assessment_v2_boundary.py`; `tests/fixtures/runtime/g12m-tushare-fixed-singleton-assessment-v2/` |
| V2-05 | sole success/blocked receipt and registry fan-in | accepted V2-01..04 on H1, or V2-01 H2 with V2-02..04 terminated | `docs/implementation/acceptance-matrix.md`; `docs/implementation/plans/g12/README.md`; `docs/implementation/plans/g12/g12m-source-bounded-qualification-v1.md`; this plan; exactly one of `docs/implementation/plans/g12/g12m-tushare-fixed-singleton-qualification-v2-h1-acceptance-receipt.md` or `docs/implementation/plans/g12/g12m-tushare-fixed-singleton-qualification-v2-h2-blocked-receipt.md` |

Edges are typed: V2-00->01 is contract; V2-01 H1->02/03/04 is authority;
V2-02->03/04 is Bundle/event evidence; V2-03->04 is verified Run evidence;
all accepted H1 tips->05 is success governance evidence. V2-01 H2 directly enters
V2-05 as blocked governance evidence and terminates V2-02..04. Shared repository/
registry files serialize V2-03 and V2-05. One implementation writer is active at a
time.

## V2-01 successor prerequisite decision

The decision type is additive v2 and must set its direct semantic predecessor to the
historical H2 decision hash `sha256:a7a6fff66a34f20031178d82fd7da424799ecbc2b3e2c887bdd149e98cc826bb`, not to the H2 receipt and not null.
It returns H1 only after exact reconstruction of accepted G07 and runnable authority
v2. It binds G12I/G12K identities and the G12K assessment-time floor but emits no
Bundle, Profile implementation, Resolution outcome, Run, proof, Integrity result,
assessment, qualification, or grade.

Any mismatch returns H2 and terminates V2-02..04. V2-05 then sets V2-01 to
`DECIDED_H2`, V2-02..04 to `TERMINATED_H2`, itself to `ACCEPTED_H2`, the route to
`BLOCKED_H2`, writes only the H2 receipt, and records no Bundle/Profile/Run/assessment
output. On H1 success, V2-01..04 and the route become `ACCEPTED_H1`, V2-05 writes only
the H1 receipt, and the H2 receipt is absent. Missing strict legal/official closure
alone is not H2 under ADR 0008.

## V2-02 exact causal execution Bundle

The Bundle has exactly three capabilities and three streams:

1. unchanged accepted `tushare_cn_a_share.daily-publications@1`: all 19 exact G12I
   `MarketEvent` values and ordered hashes;
2. unchanged accepted `precomputed_target_stream@1`: the one exact target Event;
3. Builder-owned `bar_open@1`: exactly 19 one-to-one projections, one for each
   accepted G12I Event.

Each `bar_open` projection must:

- use only source `payload.execution_reference.open_price` with exact units, scale,
  currency, instrument, provider date, and source raw/projection hashes;
- set projection `event_time == available_time == source.available_time`, as required
  by `BarOpenObservation`; preserve the source's original historical `event_time` and
  exact source `available_time` in the projection lineage preimage, while leaving the
  accepted source Event unchanged;
- retain source instrument and causal ordering;
- use exact REAL bar-open payload schema `{schema_version, bar_kind, open_price}`;
- have a new Event/source/revision identity whose canonical preimage directly binds
  source `(event_id,event_hash,revision_id,event_time,available_time)` and the exact
  selected open-price body;
- introduce no current-value inference, resampling, forward fill, gap placeholder,
  nearby price, availability rewrite, or alternative source; and
- parse through `BarOpenObservation.from_event`.

The Bundle declares no other capability. It publishes through existing G12C/D,
reopens with exact Local Reader provenance, and preserves retention/publication bytes.
Timeline order must place all 19 source Events and all 19 projections before the target
decision phase. Runtime never imports Builder or creates projections.

## V2-03 sole-facade Run

- Construct the registry only from accepted authority-v2 registrations and exact
  Build.
- Open exactly one retained Local Reader Bundle.
- Invoke the accepted v2 target validator before PREP, translation, order generation,
  or risk.
- Use one `bar_open` execution binding, no signal or valuation binding, one exact
  zero-allocation decision cycle, zero admissions, zero bar executions, empty marks,
  and zero financial side effects.
- Call only `BacktestRuntime.run(request)`; successful schema-3 decision-grade input
  must return `BacktestCanonicalPublicationRefV2`.
- Any local reopen/provenance, PREP, Resolution, durable verifier, proof publication,
  read-back, cache durability, Integrity, or canonical-v3 failure stops; no fallback to
  canonical-v2 exists.
- `load_completed_v3` must verify static graph, equal attempts, proof/canonical refs,
  and completed grade. Analysis derives and reloads through analysis v2.

Current `VerifiedCompletedPublicationV3` does not expose exact trace, resolved request,
Bundle membership, and attempt evidence required by the assessor. V2-03 may add one
additive generic verified-evidence V3 value and repository method. It may extract one
private shared graph-walk helper from the current monolithic implementation, but must
preserve `load_completed_v3` public signature, return type, failure behavior, bytes,
and verification semantics. The new projection and existing completed view must use
the same helper; no provider parser/repository, duplicate graph decoding, or root
export is allowed. Repository evidence claims static graph replay only; fresh local
durability remains facade/cache authority and must not be inferred by the repository.

The generic value minimally binds request/resolved environment, Bundle ref/manifest,
execution context/result/summary, both canonical attempts, full trace, Integrity,
proof/canonical refs, completed publication, and static/local verification identities.

## V2-04 pure assessment

The assessor imports no Builder and performs no I/O. Exact Runtime-local nominal
reconstruction of G12I/G12K canonical bytes is duplicate-key/invalid-constant safe,
exact-type, deep, subclass/duck/constructor-bypass rejecting.

Success binds:

- V2-01 authority decision and direct predecessor;
- exact authority-v2/Profile/Build/Resolution identities;
- exact V2-02 Bundle and all source/projection/target membership;
- exact V2-03 semantic Run, attempts, durable proof, Integrity result, canonical-v3
  publication, repository verification, and analysis v2;
- exactly one `TIMELINE_EVENT` trace for every accepted G12I source triple and every
  authorized bar-open projection, all strictly before the target decision phase;
- zero target effect, orders, fills, fees, settlements, lots, exposure, entitlement,
  and corporate-action dispatch;
- accounting disposition
  `ZERO_EXPOSURE_NO_ENTITLEMENT_NO_CORPORATE_ACTION_DISPATCH` without claiming action
  absence;
- existing requested/result grade copied exactly from Integrity; and
- `assessed_at >= 1787299622295499670`, limitations/nonclaims, deployment false,
  null initial assessment predecessor, and canonical assessment hash.

Failure precedence is exact: input type; canonical/source reconstruction; successor
authority; Bundle/source/projection membership; target/singleton; Run/attempt/proof;
Resolution/Integrity grade; Timeline causality; accounting; assessment time;
predecessor; final reconstruction. Failures contain only code and canonical subject
identities.

## Grade, correction, and nonclaim firewalls

Resolution alone decides compatibility and Integrity alone decides result grade.
G12M copies; it never mints/upgrades/downgrades. Evidence/Run Bundles may differ only
when exact membership lineage is proven. Source corrections require accepted upstream
G12I/G12K successors, a direct successor prerequisite decision, new Profile semantic
identity, new Bundle/Run, and direct-successor assessment. No synthetic correction
success path is required.

This route remains fixed-singleton, historical, source-bounded, no-trade, non-live,
and non-deployment. It does not claim historical Provider Availability Time, provider
finality/completeness, listing continuity, survivorship, corporate-action lifecycle or
absence, strict official/legal/tax closure, execution quality, live eligibility, or
Binance qualification.

## V2-05 acceptance closure

At main/candidate `2f2bc40cc5fcd06f4f47af9c5c6e691fee00f7a6`, V2-01,
V2-02, V2-03, V2-04, V2-05, and the route are `ACCEPTED_H1`. The sole receipt is
[g12m-tushare-fixed-singleton-qualification-v2-h1-acceptance-receipt.md](g12m-tushare-fixed-singleton-qualification-v2-h1-acceptance-receipt.md)
(`sha256:28c94f5530bdf4bf74707a0ece33c3d2b70ffb51c3d061b4950e17d6de58998c`);
the H2 receipt is absent.

The accepted implementation is additive schema 4 for the execution-input Bundle:
manifest/content `sha256:2ea4d3c58076312ff86ee175fac2f1173fb28f01e4e4d31ca372ca0d345e750b` /
`sha256:a0b6319c07aaa810ba490924f2267ebb93f72d5037432b30dd6a0a5bbb3fb8ff`.
This closure does not rewrite the frozen historical schema-3 contract clause above.
It records the accepted catalog fan-in while retaining the sole facade and authority
order. The accepted route is
`sha256:49051c693cd2ea4c1822c6e8ac6f929e0e952ccba8cfa7d5d248e18d9b7eb0f2`,
the semantic Run is
`run_1eebd60b81376e15fbe4b2496ed359ab24ed644c7416812d09eb3fb715f581a9`,
and the final assessment is
`sha256:31f29b9ab70e7c8da267b6c17dcbe294503088850c894b066116313233dca8bb`.
The assessment binds 19 source Events, 19 projections, one target, 39 Timeline
Events, zero trade/accounting effects, copied `decision_grade`, and assessment time
at or after `1787299622295499670`.

Historical Tushare v1 H2 and Binance H3 `NO_CAUSAL_AUTHORITY` remain unchanged. All
provider availability/finality/completeness, listing/survivorship,
corporate-action lifecycle/absence, strict legal/tax closure, execution-quality,
live/deployment, and Binance-qualification nonclaims remain in force.

## Validation budget

- V2-01: canonical decision/manifest replay and independent authority review.
- V2-02: focused Builder/G12C/D/Reader plus causality/lineage mutation tests.
- V2-03: focused facade/PREP/Resolution/Integrity/durable proof/repository/analysis,
  then full suite because shared repository files change.
- V2-04: focused adversarial assessor, adjacent Runtime, then full acceptance suite.
- V2-05: protected G12I/G12K/Binance/v1/v2 hashes, links/status, diff, gitleaks, and
  independent final review.

No node edits accepted G12I/G12K/Binance, authority v1/v2, canonical-v1/v2, or public
facade bytes. No push is authorized.
