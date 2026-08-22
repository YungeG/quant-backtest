---
id: G12M-TUSHARE-FIXED-SINGLETON-PROFILE-BUILD-AUTHORITY-V1
status: ACCEPTED
owner: independent China A-share Profile/Build authority lane
---

# Fixed-singleton China A-share Profile/Build authority v1

## Purpose

Create an independent production Profile/Build authority for exactly one case: fixed `xshe:000001`, no selector, accepted Tushare daily scope `2026-07-06` through `2026-07-31` exclusive, zero initial/final exposure, one precomputed zero target, and no orders, fills, fees, settlement, lots, or corporate-action dispatch. This lane is independent of the G12M assessor and BHA-03.

The target decision instant is `1787292861381694497`, exactly one nanosecond after the latest accepted G12I local member acquisition/receipt time `1787292861381694496`. The event is at that same instant in timeline phase `(30, strategy_decision)`. This does not claim historical Provider Availability Time.

## Candidate write set

Only these additive paths are authorized:

- `packages/backtest-runtime/src/crypto_quant_backtest/cn_a_share_fixed_singleton_no_trade_profile_v1.py`
- `tests/runtime/profiles/cn_a_share/test_fixed_singleton_no_trade_profile_v1.py`
- `tests/architecture/test_cn_a_share_fixed_singleton_no_trade_profile_boundary.py`
- this plan
- `docs/research/g12m-tushare-fixed-singleton-profile-build-authority-v1.md`
- `evidence/g12m-tushare-fixed-singleton-profile-build-authority-v1/decision.json`
- `evidence/g12m-tushare-fixed-singleton-profile-build-authority-v1/manifest.sha256`

There is no root export, shared registry/resolver/PREP/facade/Integrity edit, existing fixture edit, dependency, G12M assessor or adapter, or Matrix/G12 README change.

## Exact candidate

The private module exposes one immutable authority value, one exact constructor, and one exact target-stream validator. It uses existing `PrecomputedTargetStream`, Profile registration, Resolution, and `BuildArtifactManifest` contracts directly; it defines no registry, framework, Builder, assessor, adapter, or DSL.

The frozen identities are:

| Identity | SHA-256 |
| --- | --- |
| semantic authority | `sha256:a0f0fb905dbc34d877c39130bf615f2f5d725b97aa618ed97bffdd1a12bce654` |
| target commitment | `sha256:8e4bdddbd91e1bafd65363e133d382673df88e4dc4061d1f0dd776a42afc6cee` |
| Market Profile | `sha256:c04c32477654531c643c7bdc3527bf5a3c52671581a1444b864ac685f0b0a8e7` |
| Simulation Profile | `sha256:c21f8a46546690bb5227e6bf228418daa56d8becb9a4506cc649bd7fde2acc8f` |
| Account Profile | `sha256:bac4efa7e4874d3ab915ae6d775c3213db29c12c992663e065dc363ac8c78406` |
| Build manifest | `sha256:a6a73cb72a9ad4cf98bca789c19a6a261f00dc4b1e538478a0ca9674137ab516` |

All registrations request `RequestedResultGrade.DECISION_GRADE`, are decision-grade eligible, have no limitations, and do not authorize deployment. Market requires only `tushare_cn_a_share.daily-publications@1`; Simulation requires only `precomputed_target_stream@1`. Resolution therefore needs exactly those two capabilities and no `bar_open`, corporate-action, or financial-event capability.

The Build binds the target digest as `DECISION_SOURCE`, each Profile registration digest as `PROFILE_COMPONENT`, deterministic source-snapshot preimages for the four generic core roles at candidate `cebb9b033b7eeffbbff712715fc017708ac5a247`, lock hash `sha256:a97b6708411bcec45f23504cc41b3a2b54c80d9272a6deb3f2800be891e9b41d`, and CPython 3.13.5 binary hash `sha256:4703a3d15898c0b5d81c3f939e93bdd8ca6116342093fb160ab1e01860dd7d8b`. Build provenance uses the accepted candidate commit time `1787391728000000000` rather than the historical decision instant. Every install mode is non-editable. No retained wheel-byte claim is made.

## Applicability contract

- Session and instrument identity are active only for the fixed July-2026 `xshe:000001` scope.
- Order-rule, fee, tax, settlement, and position-accounting ports are inert because order capacity is zero.
- Financing, margin, liquidation, corporate action, currency valuation, liquidation audit, and closeout are inert because exposure is zero.
- Existing development-named execution, zero-slippage, zero-latency, and full-fill liquidity refs retain those names and are bound only as `INERT_BY_ZERO_TARGET_AND_ZERO_ORDER_CAPACITY`; they are not renamed or generalized.
- The Account risk policy is active and has `order_capacity_limit=0`. This is independent defense after the exact zero-target validator, never a substitute for that target authority.

The canonical authority exact-covers every `ProfilePortType` and `SimulationPortType`. Any ref, disposition, source, registration, Build, target, or authority-hash mismatch fails exact reconstruction.

## Source and generic-proof bindings

The authority binds accepted G12I report/file `ff09c4ad…` / `9cbfc115…` at Assessment Time `1787292861381694496`, accepted G12K report/file `5a49065d…` / `a386f428…` at later Assessment Time `1787299622295499670`, G07 contract `30a2f612…`, deterministic golden `33f26207…`, Backtest governance commit `606b7e866673f3a5eb71a69196687dd653561b42`, Platform consumer commit `5948dd62f50d197f3e35d499a8e44e04b2257981`, and Platform gitlink candidate `cebb9b033b7eeffbbff712715fc017708ac5a247`. Provider qualification flags remain false and do not set Profile or result grade. The target Event/source hash binds only decision-available G12I; G12K remains post-decision Profile/qualification authority evidence and cannot appear in target evidence. Any future G12M assessment must occur no earlier than the G12K Assessment Time. Initial predecessor is null.

## Nonclaims

Strict G12H successor/official/legal/tax/compliance closure, historical listing membership, corporate-action lifecycle, historical Provider Availability Time, provider completeness, and provider future-revision finality are explicit nonclaims. Under ADR 0008 they are not limitations of this exact zero-exposure/no-trade Profile. This candidate does not mint G12M qualification or `ResultGrade`, authorize live use or deployment, execute a Run, or produce an assessment.

## Accepted fan-in

The exact candidate is accepted at immutable commit `c52c8913ef680b34c1edecf46b1892b268e013e0` (parent `606b7e866673f3a5eb71a69196687dd653561b42`). Its seven-path write set is the module, two focused tests, this plan, the research report, canonical decision, and manifest.

Validation evidence:

- clean-worktree broad-regression baseline: `uv run pytest -q` = `2320 passed` before the final narrow time/provenance/causal-binding corrections;
- final candidate focused tests: `12 passed`;
- final Ruff, primary LSP, compileall, diff-check, gitleaks, canonical hash replay, exact write-set, DEVELOPMENT/root protected hashes, and two independent reviews: PASS;
- semantic authority `sha256:a0f0fb905dbc34d877c39130bf615f2f5d725b97aa618ed97bffdd1a12bce654`;
- canonical decision file `sha256:0a22eb7368eb0838d772efbcd6fc08cf48d333783d3ae881a12ba304f25ae1ca`;
- target commitment `sha256:8e4bdddbd91e1bafd65363e133d382673df88e4dc4061d1f0dd776a42afc6cee`;
- Build manifest `sha256:a6a73cb72a9ad4cf98bca789c19a6a261f00dc4b1e538478a0ca9674137ab516`.

Acceptance does not reopen, supersede, or mutate the old BHA-01 H2 decision or any BHA-02 through BHA-05 artifact. It authorizes only an additive successor G12M route to bind this authority together with accepted G07 durable-proof authority. Future execution must explicitly invoke the exact target validator before translation/risk, and any assessment consuming G12K must occur no earlier than `1787299622295499670`.
