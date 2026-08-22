# G12M Tushare fixed-singleton Profile/Build authority v1

## Result

An independent candidate authority now exists for the exact production no-trade case. Its canonical decision is [decision.json](../../evidence/g12m-tushare-fixed-singleton-profile-build-authority-v1/decision.json), semantic authority hash `sha256:a0f0fb905dbc34d877c39130bf615f2f5d725b97aa618ed97bffdd1a12bce654`, decision-file SHA-256 `sha256:0a22eb7368eb0838d772efbcd6fc08cf48d333783d3ae881a12ba304f25ae1ca`, target digest `sha256:8e4bdddbd91e1bafd65363e133d382673df88e4dc4061d1f0dd776a42afc6cee`, and Build manifest hash `sha256:a6a73cb72a9ad4cf98bca789c19a6a261f00dc4b1e538478a0ca9674137ab516`.

This is a Profile/Build authority candidate, not G12M qualification, an assessor result, Integrity grade, Run, live authorization, or deployment authorization.

## Fixed authority boundary

| Fact | Exact authority |
| --- | --- |
| Instrument | singleton `xshe:000001`; no dynamic selector |
| Accepted source scope | Tushare daily publications from `2026-07-06` through `2026-07-31` exclusive |
| Latest accepted local member Acquisition/Receipt Time | `1787292861381694496` |
| Decision/event instant | `1787292861381694497`, exactly one nanosecond later |
| Timeline phase | rank `30`, code `strategy_decision` |
| Target | exactly one target for `xshe:000001`, canonical value `0` |
| Exposure | zero initially and finally |
| Trading side effects | zero orders, fills, fees, settlements, lots, and corporate-action dispatches |
| Account defense | active exact risk policy with `order_capacity_limit=0` |

The local acquisition cut is not a claim about historical Provider Availability Time. The target is a valid exact `PrecomputedTargetStream` and binds only decision-available G12I evidence; later G12K assessment evidence is excluded from the target payload and source hash. Its one `MarketEvent`, envelope, candidate, evidence mapping, source identity, source hash, event hash, count, timing, phase, singleton instrument, zero value, and stream digest are committed. Validation requires the exact class and canonical byte equality. Empty, nonzero, extra-instrument, extra-event, wrong-count, wrong-time, wrong-phase, wrong-source, wrong-hash, wrong-stream, and changed-digest forms fail before execution. A focused `PrecomputedTargetStreamAdapter` test proves the retained payload decodes to one target with units zero.

## Component-by-component applicability

### Market/Profile ports

| Port | Bound component key | Disposition | Independent justification |
| --- | --- | --- | --- |
| `session_model` | `equity.cn_a_share.fixed-july-2026-session.v1` | active fixed-case authority | Only the exact accepted July-2026 finite scope is identified; no general exchange calendar or current-selected G12H claim is made. |
| `instrument_model` | `equity.cn_a_share.fixed-xshe-000001.v1` | active fixed-case authority | G12K binds the fixed instrument identity used by this no-selector case; it does not establish a dynamic universe. |
| `order_rule_model` | `equity.cn_a_share.cash.order-rules.v1` | inert by zero order capacity | No order can be admitted, so no order-rule result can affect state. |
| `fee_assessment_policy` | `equity.cn_a_share.cash.market-fees.route-product.v2` | inert by zero order capacity | No admitted order or fill exists from which a fee can arise. |
| `tax_policy` | `equity.cn_a_share.cash.stamp-duty.route-product.v2` | inert by zero order capacity | No admitted trade or taxable disposition exists. |
| `settlement_model` | `equity.cn_a_share.cash.settlement.v1` | inert by zero order capacity | No order, fill, cash movement, or lot exists to settle. |
| `position_accounting_model` | `cash.instrument.position-accounting.v1` | inert by zero order capacity | No admitted order/fill can create a position-accounting mutation. |
| `financing_model` | `cash.no-financing.v1` | inert by zero exposure | The case has no position, borrowing, cash deficit, or financing event. |
| `margin_model` | `cash.no-margin.v1` | inert by zero exposure | Zero exposure and cash-only account semantics make margin unreachable. |
| `liquidation_rules` | `equity.cn_a_share.cash.liquidation-not-applicable.v1` | inert by zero exposure | No exposure exists to liquidate. |
| `corporate_action_model` | `equity.cn_a_share.corporate-action.inert-zero-exposure.v1` | inert by zero exposure | No held lot or entitlement exists; dispatch count is fixed at zero. |
| `currency_valuation_policy` | `equity.cn_a_share.cny-identity-valuation.v1` | inert by zero exposure | There is no position or cash-flow valuation result to transform. |

### Simulation ports

| Port | Bound component key | Disposition | Independent justification |
| --- | --- | --- | --- |
| `execution_model` | `next_eligible_bar_open.v1` | inert by zero target and zero order capacity | The retained development-era name is not generalized; no order reaches execution, so no `bar_open` capability is required. |
| `slippage_model` | `zero_slippage.development.v1` | inert by zero target and zero order capacity | The development name remains explicit and cannot qualify active slippage; no fill price is produced. |
| `latency_model` | `latency.zero.development.v1` | inert by zero target and zero order capacity | No order lifecycle exists on which latency could act. |
| `liquidity_model` | `liquidity.next-bar-full-fill.development.v1` | inert by zero target and zero order capacity | The development full-fill model is never invoked and is not relabeled as production liquidity authority. |
| `liquidation_audit_model` | `cash.no-liquidation-audit.v1` | inert by zero exposure | No liquidation transition can occur. |
| `closeout_policy` | `mark_to_market.v1` | inert by zero exposure | Final exposure is zero, so closeout has no position to mark or terminate. |

The exact applicability tuple covers every current `ProfilePortType` and `SimulationPortType` once. Registration identity incorporates the accepted source identities, target commitment, and applicability hash. Any source or applicability mutation changes semantic identity and fails the accepted constants.

## Profile and Resolution authority

The new registrations are distinct from and do not reuse `CnAShareResolvedProfile`:

| Registration | Key | Digest |
| --- | --- | --- |
| Market | `equity.cn_a_share.fixed-singleton-no-trade.market.v1` | `sha256:c04c32477654531c643c7bdc3527bf5a3c52671581a1444b864ac685f0b0a8e7` |
| Simulation | `backtest.cn_a_share.fixed-singleton-no-trade.simulation.v1` | `sha256:c21f8a46546690bb5227e6bf228418daa56d8becb9a4506cc649bd7fde2acc8f` |
| Account | `account.cn_a_share.fixed-singleton-no-trade.cash.v1` | `sha256:bac4efa7e4874d3ab915ae6d775c3213db29c12c992663e065dc363ac8c78406` |

All three request `DECISION_GRADE`, set `decision_grade_eligible=True`, carry `limitations=()`, and keep deployment false. Market requires exactly `tushare_cn_a_share.daily-publications@1`; Simulation requires exactly `precomputed_target_stream@1`. A synthetic Bundle with exactly those two capabilities resolves successfully at decision grade with no environment limitations. Missing Profile artifacts, editable artifacts, dependency-lock/build-reference mismatch, and component identity mismatch fail closed.

The existing DEVELOPMENT module remains byte-identical at `sha256:f5ec4c572b6bb84fe94997051b9d382be6e3a0a9e227b1fea56a193113114a3c`; the Runtime root remains byte-identical at `sha256:05b1e1520ac31e8b094de195962ffea395441c823286ca95e868add22a5bfe02`. No public root export was added.

## Accepted evidence and proof identities

Provider evidence remains evidence only:

- G12I report `sha256:ff09c4ad9f8025e66689387b5132d3d85c4101276fbf7330dd5040af111cc029`, canonical file `sha256:9cbfc115e41f56d1e83eac520856c3f529f83972b97111238e5dbb1a68c4eae6`, Assessment Time `1787292861381694496`;
- G12K report `sha256:5a49065d87286a9673893337328ddbbab9a19cd3addf178bf96033b9b1babfd7`, canonical file `sha256:a386f4281374d1449c0b5ba4371b9e9d2de5b236bc8fc5b5cdd8de5e43c65956`, Assessment Time `1787299622295499670`.

Every recorded provider qualification/grade/live/deployment flag remains false. Those flags cannot set Profile or result grade. Because G12K Assessment Time is later than the target decision, G12K is bound only into the Profile/Build authority and any later qualification assessment; it is not target-decision evidence.

The independently accepted generic proof prerequisite is bound by G07 contract `sha256:30a2f6127969a58c946e8fde6369515aa236f7bac89c4e039ea35e7fce4f8be7`, deterministic verification golden `sha256:33f262070a59ce52a350b99dcffdd9548a0643755690beeda9afffbada20aad7`, Backtest governance commit `606b7e866673f3a5eb71a69196687dd653561b42`, Platform consumer commit `5948dd62f50d197f3e35d499a8e44e04b2257981`, and gitlink candidate `cebb9b033b7eeffbbff712715fc017708ac5a247`. This authority consumes those identities; it does not redesign or self-attest the proof seam.

## Build authority

The exact `BuildArtifactManifest` has hash `sha256:a6a73cb72a9ad4cf98bca789c19a6a261f00dc4b1e538478a0ca9674137ab516`, all required roles, no editable install, immutable identities for every artifact, `limitations=()`, and `decision_grade_eligible=True`.

- `DECISION_SOURCE.content_hash` is the exact target commitment digest.
- The three `PROFILE_COMPONENT.content_hash` values are the exact registration digests.
- Trading Domain, Trading Kernel, Market Data Contracts, and Backtest Runtime use deterministic canonical source-snapshot preimages bound to generic candidate `cebb9b033b7eeffbbff712715fc017708ac5a247`.
- Dependency lock is `sha256:a97b6708411bcec45f23504cc41b3a2b54c80d9272a6deb3f2800be891e9b41d`.
- Runtime is CPython `3.13.5` with binary hash `sha256:4703a3d15898c0b5d81c3f939e93bdd8ca6116342093fb160ab1e01860dd7d8b`.
- Build provenance `built_at` is the accepted `cebb9b0…` candidate commit time `1787391728000000000`, not the historical target decision instant.
- Authority identity contains no local absolute path, hostname secret, or environment value. No retained wheel-byte claim is needed or made.

## Limitations and nonclaims

Profile, Build, and resolved-environment limitations are empty because historical Provider Availability Time, provider future finality, provider-global completeness, and strict G12H official/legal closure are G12M assessment nonclaims under ADR 0008, not applicable blockers for this exact zero-exposure/no-trade Profile. This does not turn those unknown facts true.

The authority explicitly does not claim strict legal/tax/compliance closure, historical listing membership, corporate-action lifecycle, historical Provider Availability Time, provider completeness, future revision finality, retained wheel bytes, G12M qualification, a new grade, live eligibility, deployment, a completed Run, or an Integrity result. Initial predecessor is null. Any future G12M assessment consuming G12K must occur no earlier than `1787299622295499670`.

## Governance route

This candidate is additive and independent. A later, separate governance fan-in may bind its immutable commit into the Acceptance Matrix and G12 README and then allow BHA-01 prerequisite reconsideration. This candidate commit does not mutate or reopen the accepted old H2 decision and does not produce BHA-02/BHA-03/BHA-04 work.
