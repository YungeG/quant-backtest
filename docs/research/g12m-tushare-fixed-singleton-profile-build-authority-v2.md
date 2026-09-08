# G12M Tushare fixed-singleton Profile/Build authority v2

## Result

A runnable additive successor now exists for the exact accepted fixed-singleton no-trade case. Its semantic authority hash is `sha256:3d19c05e552aa61a7f1ff33bc2451d2d0cc13e0d3ee30acde46462bdfa65becf`, canonical decision file hash is `sha256:8b1da7ec4aaa4b652f69ce569ed0df953e8b9e30937368e9b32396baf090f21a`, and Build hash is `sha256:26048a80c045b8c49ab4f09936ab6ea3ef31acd767d54365caa20c8e457f7f45`.

Accepted v1 remains immutable at candidate `c52c8913ef680b34c1edecf46b1892b268e013e0` and governance acceptance `0c0a7df5b1f4b6d83928fec0b19d60696ff20d72`, semantic authority `sha256:a0f0fb905dbc34d877c39130bf615f2f5d725b97aa618ed97bffdd1a12bce654`, decision file `sha256:0a22eb7368eb0838d772efbcd6fc08cf48d333783d3ae881a12ba304f25ae1ca`, target `sha256:8e4bdddbd91e1bafd65363e133d382673df88e4dc4061d1f0dd776a42afc6cee`, and Build `sha256:a6a73cb72a9ad4cf98bca789c19a6a261f00dc4b1e538478a0ca9674137ab516`. V2 directly supersedes that authority for production Runtime composition; it does not reinterpret v1.

## Why v1 cannot be used as runnable composition

Runtime tracing proved two exact-contract mismatches:

1. v1 generated a semantic ref named `next_eligible_bar_open.v1`, but its digest is not the digest created by the real `NextEligibleBarOpenModel.create` constructor.
2. v1 Simulation required only `precomputed_target_stream@1`, while the real model's spec unconditionally requires `bar_open@1` and PREP validates that capability/binding even when no order reaches execution.

Constructor bypass would violate exact Runtime type/digest validation. Therefore name equality, inert applicability, and ProfileResolver success cannot establish runnable authority. V1 bytes remain accepted evidence of the prior decision, but its Market/Simulation composition is superseded.

## Preserved authority

V2 reuses the exact v1 case, accepted G12I/G12K source identities, G07 durable-proof identities, timestamps, zero target stream, Account risk policy/registration, and nonclaims. The target validator is an exact delegate to v1 and additionally remains bound by the authority's deep reconstruction. G12K is still post-decision Profile/assessment evidence only; it does not appear in target evidence or alter target bytes.

The exact target remains one zero target for `xshe:000001` at `1787292861381694497`, one nanosecond after the accepted G12I local member receipt/acquisition time. Exposure, orders, fills, fees, settlement, lots, and corporate-action dispatch remain zero.

## Actual component binding

V2 constructs the exact real execution model with complete TIF behavior:

| TIF | no-eligible-bar action |
| --- | --- |
| DAY | EXPIRE |
| GTC | KEEP_ACTIVE |
| IOC | EXPIRE |
| FOK | EXPIRE |
| GTX | KEEP_ACTIVE |

The result is `next_eligible_bar_open.v1` with component digest `sha256:d69d6d96c9081f730db6ff8cdd02431d4babdef2e3967f0094971e73aedf30fe` and exact required capability `bar_open@1`.

V2 also constructs `MarkToMarketCloseoutPolicy` and `default_cash_financial_dispatcher_spec`. The following six refs are replaced by actual Runtime refs, with predecessor refs and applicability dispositions retained in authority evidence:

- Simulation execution model;
- Simulation closeout policy;
- Simulation liquidation audit model;
- Market position accounting model;
- Market financing model;
- Market margin model.

Every other v1 component ref remains byte-equal, including development-named zero-slippage, zero-latency, full-fill-liquidity assumptions and the fixed market-rule, fee, tax, settlement, corporate-action, and currency refs. They remain explicitly inert under the same zero-target, zero-order-capacity, or zero-exposure boundary.

## Profiles, capabilities, and Build

| Registration | Key/version | Digest |
| --- | --- | --- |
| Market v2 | `equity.cn_a_share.fixed-singleton-no-trade.market.v2@2` | `sha256:52b02b86b4fb6ea0b481d1184f68148d8b3d074b93e332ca582cd417072c8fd1` |
| Simulation v2 | `backtest.cn_a_share.fixed-singleton-no-trade.simulation.v2@2` | `sha256:a1f0e4dd163deebf7dd8cf10e199078b6ad1c68bf0467b1f7f449e3423114875` |
| Account v1 reused | `account.cn_a_share.fixed-singleton-no-trade.cash.v1@1` | `sha256:bac4efa7e4874d3ab915ae6d775c3213db29c12c992663e065dc363ac8c78406` |

Market requires exactly `tushare_cn_a_share.daily-publications@1`. Simulation requires exactly sorted `bar_open@1` and `precomputed_target_stream@1`. All registrations request `DECISION_GRADE`, are eligible, carry empty limitations, and do not authorize deployment.

The Build retains exact v1 target and Account artifacts; exact accepted `cebb9b033b7eeffbbff712715fc017708ac5a247` Trading Domain, Trading Kernel, Market Data Contracts, and Runtime source-snapshot identities; lock hash `sha256:a97b6708411bcec45f23504cc41b3a2b54c80d9272a6deb3f2800be891e9b41d`; and CPython 3.13.5 binary `sha256:4703a3d15898c0b5d81c3f939e93bdd8ca6116342093fb160ab1e01860dd7d8b`. Only Market/Simulation Profile artifacts are replaced. Operational provenance remains the exact accepted underlying generic Runtime snapshot `cebb9b033b7eeffbbff712715fc017708ac5a247` at `1787391728000000000`; c52/0c0 identify predecessor authority acceptance, not a v2 source build. All artifacts are immutable and noneditable, required roles are present, decision-grade eligibility is true, and limitations are empty.

## PREP execution proof

The critical test uses public `prepare_multi_resolution_market_data_v1`, not only ref/spec assertions or ProfileResolver. It builds one exact in-memory Bundle with daily-publications, the immutable v1 target stream, and one valid REAL `bar_open@1` event. The resolved case uses the exact authority execution model, empty valuation marks, no admissions, and no bar executions.

Current PREP requires every retained target event to be exact-covered by a decision cycle. The test therefore supplies one zero-allocation target cycle with zero admissions; this is the smallest public successful equivalent of the intended empty execution case. Preparation succeeds with one exact execution binding. A resolved v1 execution ref, absent execution binding, binding to the wrong-capability target stream, missing `bar_open@1`, subclasses, and constructor-bypass mutations fail closed.

This proves the execution model/ref/spec/capability tuple is accepted by the retained-reader PREP path. It does not claim that v2 publishes provider projection bytes.

## Future causal bar-open projection

A future Builder must publish an exact causal `bar_open@1` projection from accepted G12I `execution_reference.open_price`. V2 authorizes only the required component and capability. It does not mint the projection event, choose substitute price bytes, infer a current value, or establish additional provider availability/completeness.

## Nonclaims

This authority does not qualify G12M, Tushare or any provider, historical Provider Availability Time, provider revision completeness, official/legal/tax/compliance closure, listing/corporate-action lifecycle, live eligibility, deployment, a completed Run, an Integrity result, or a new `ResultGrade`. G12K remains Profile/assessment evidence after the decision instant. No root, shared PREP/resolver/facade/Integrity/repository, Builder, Matrix, or G12 README surface changes.
