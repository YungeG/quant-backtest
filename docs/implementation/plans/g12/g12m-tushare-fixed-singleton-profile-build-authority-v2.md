---
id: G12M-TUSHARE-FIXED-SINGLETON-PROFILE-BUILD-AUTHORITY-V2
status: CANDIDATE
owner: independent China A-share Profile/Build authority lane
---

# Fixed-singleton China A-share Profile/Build authority v2

## Purpose

Publish an additive runnable successor to accepted v1 for exactly the same fixed `xshe:000001` zero-target/no-trade case. Accepted v1 at candidate commit `c52c8913ef680b34c1edecf46b1892b268e013e0` remains immutable. V2 does not reinterpret or alter v1 target, case, source, G07, time, Account, or nonclaim bytes.

Runtime tracing showed why a successor is necessary: v1's semantic-generated `next_eligible_bar_open.v1` ref is not the exact ref created by `NextEligibleBarOpenModel.create`, and v1 Simulation omits the model's unconditional `bar_open@1` PREP capability. Constructor bypass is forbidden, so v1 cannot be repaired in place or treated as runnable by name alone. V2 supersedes v1 only for production Runtime composition.

## Candidate write set

Only these additive paths are authorized:

- `packages/backtest-runtime/src/crypto_quant_backtest/cn_a_share_fixed_singleton_no_trade_profile_v2.py`
- `tests/runtime/profiles/cn_a_share/test_fixed_singleton_no_trade_profile_v2.py`
- `tests/architecture/test_cn_a_share_fixed_singleton_no_trade_profile_v2_boundary.py`
- this plan
- `docs/research/g12m-tushare-fixed-singleton-profile-build-authority-v2.md`
- `evidence/g12m-tushare-fixed-singleton-profile-build-authority-v2/decision.json`
- `evidence/g12m-tushare-fixed-singleton-profile-build-authority-v2/manifest.sha256`

There is no v1, shared facade/PREP/resolver/Integrity/repository, root, Builder, Matrix, G12 README, registry, factory, framework, DSL, dependency, provider adapter, or assessor edit.

## Frozen predecessor and result identities

| Identity | SHA-256 / commit |
| --- | --- |
| predecessor candidate | `c52c8913ef680b34c1edecf46b1892b268e013e0` |
| predecessor governance | `0c0a7df5b1f4b6d83928fec0b19d60696ff20d72` |
| v1 semantic authority | `sha256:a0f0fb905dbc34d877c39130bf615f2f5d725b97aa618ed97bffdd1a12bce654` |
| v1 decision file | `sha256:0a22eb7368eb0838d772efbcd6fc08cf48d333783d3ae881a12ba304f25ae1ca` |
| unchanged v1 target | `sha256:8e4bdddbd91e1bafd65363e133d382673df88e4dc4061d1f0dd776a42afc6cee` |
| predecessor v1 Build | `sha256:a6a73cb72a9ad4cf98bca789c19a6a261f00dc4b1e538478a0ca9674137ab516` |
| v2 semantic authority | `sha256:3d19c05e552aa61a7f1ff33bc2451d2d0cc13e0d3ee30acde46462bdfa65becf` |
| v2 decision file | `sha256:8b1da7ec4aaa4b652f69ce569ed0df953e8b9e30937368e9b32396baf090f21a` |
| v2 Market Profile | `sha256:52b02b86b4fb6ea0b481d1184f68148d8b3d074b93e332ca582cd417072c8fd1` |
| v2 Simulation Profile | `sha256:a1f0e4dd163deebf7dd8cf10e199078b6ad1c68bf0467b1f7f449e3423114875` |
| reused exact Account Profile | `sha256:bac4efa7e4874d3ab915ae6d775c3213db29c12c992663e065dc363ac8c78406` |
| v2 Build | `sha256:26048a80c045b8c49ab4f09936ab6ea3ef31acd767d54365caa20c8e457f7f45` |

`supersedes_authority_hash` is the exact v1 semantic authority hash. The predecessor body also binds the immutable v1 governance acceptance commit, so the successor does not treat the unaccepted candidate tip alone as authority. The v2 target validator delegates to the exact v1 validator; canonical target bytes are unchanged. G12K remains post-decision Profile/assessment evidence only and is absent from the target payload/source identity.

## Exact runnable Runtime composition

V2 constructs the real `NextEligibleBarOpenModel` using these five complete TIF actions:

- `DAY -> EXPIRE`
- `GTC -> KEEP_ACTIVE`
- `IOC -> EXPIRE`
- `FOK -> EXPIRE`
- `GTX -> KEEP_ACTIVE`

Its exact component ref is `sha256:d69d6d96c9081f730db6ff8cdd02431d4babdef2e3967f0094971e73aedf30fe`; its exact spec requires `bar_open@1`.

V2 also constructs the exact `MarkToMarketCloseoutPolicy` and `default_cash_financial_dispatcher_spec`. Their actual refs replace v1 semantic-generated refs for execution, closeout, liquidation audit, position accounting, financing, and margin. Each replacement records its predecessor ref and fixed-case applicability disposition. Session, instrument, order-rule, fee, tax, settlement, liquidation-rule, corporate-action, currency, and development-named slippage/latency/liquidity refs remain exactly v1 and explicitly inert where applicable.

The new Market key/version is `equity.cn_a_share.fixed-singleton-no-trade.market.v2@2`; the new Simulation key/version is `backtest.cn_a_share.fixed-singleton-no-trade.simulation.v2@2`. The exact v1 Account registration is reused. All registrations request `DECISION_GRADE`, set eligibility true, carry no limitations, and do not authorize deployment. Market requires only `tushare_cn_a_share.daily-publications@1`. Simulation requires exactly sorted `bar_open@1` and `precomputed_target_stream@1`.

## Build authority

The v2 Build retains the exact v1 target `DECISION_SOURCE`, exact Account artifact, accepted `cebb9b033b7eeffbbff712715fc017708ac5a247` core artifact versions/source-snapshot identities, dependency lock `sha256:a97b6708411bcec45f23504cc41b3a2b54c80d9272a6deb3f2800be891e9b41d`, and CPython 3.13.5 runtime identity `sha256:4703a3d15898c0b5d81c3f939e93bdd8ca6116342093fb160ab1e01860dd7d8b`. It replaces only v1 Market/Simulation `PROFILE_COMPONENT` artifacts with v2 digests. Operational Build provenance remains the exact accepted v1 underlying generic Runtime snapshot (`cebb9b033b7eeffbbff712715fc017708ac5a247`, built at `1787391728000000000`); c52/0c0 authority candidate and governance identities are bound separately as predecessor authority, not misreported as v2 Build provenance. Every artifact has an immutable identity and a noneditable install mode; required roles exact-cover and Build limitations are empty.

## Runnable PREP acceptance

The focused acceptance test constructs one exact in-memory Bundle reader containing:

- declared `tushare_cn_a_share.daily-publications@1`;
- the exact immutable v1 target stream;
- one syntactically valid REAL `bar_open@1` event.

It resolves the v2 request/Build, creates an empty-position/empty-mark zero-trade `MarketDataCaseAuthority` with the exact v2 execution model, no admissions, no bar executions, and an empty snapshot projection, then calls public `prepare_multi_resolution_market_data_v1` with one execution binding. Current PREP requires the accepted target stream to be exact-covered by one decision cycle, so the synthetic case carries one zero-allocation target cycle; it still has zero orders and executions. PREP succeeds. Missing/wrong execution bindings and a resolved v1 execution ref fail with `EXECUTION_PROFILE_BINDING_MISMATCH`; missing `bar_open@1` fails Resolution. Exact-type/subclass and constructor-bypass mutations fail closed.

## Projection boundary and nonclaims

V2 authorizes the exact execution component and required capability only. It does not publish or authorize causal `bar_open` projection bytes. A future Builder must publish the exact causal bar-open projection from accepted G12I `execution_reference.open_price`, preserving source identity and timing; it may not infer a current or alternative price.

V2 does not qualify G12M, a provider, official/legal/tax/compliance completeness, live use, deployment, a Run, an Integrity result, or any new grade. V1 remains accepted and immutable, but production Runtime composition must use this v2 successor because the v1 execution ref/capability pair is not exact PREP authority.
