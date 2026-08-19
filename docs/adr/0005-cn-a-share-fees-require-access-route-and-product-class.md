# ADR 0005: China A-share Execution Fees Require Access Route and Product Class

- Status: Accepted
- Date: 2026-08-19
- Scope: G08E v2, G08H additive binding, G12H

## Context

G08E v1 intentionally accepts a route- and product-blind `CnAShareCashFeeRuleQuery`. Its finite August-2023 fixtures are valid only under the G08H caller precondition for an ordinary domestic CNY cash-auction A share. G12H F1 showed that this precondition cannot support a reusable July-2026 fee authority: Northbound ordinary A shares add an HKSCC trade-notional transfer charge, preferred-stock handling differs from ordinary-stock handling, and Northbound ETFs have a distinct handling and waiver schedule.

`InstrumentType.EQUITY`, symbol text, `InstrumentId.stable_key`, board, account permission, or documentation cannot stand in for the route and product actually selected for execution. A route-only discriminator is also insufficient. Non-notional portfolio, instruction, and settlement charges require different state and bases and cannot be blended into a trade-notional rate.

## Decision

Add a separate execution-fee v2 contract. Do not modify, reinterpret, or migrate any G08E/G08H v1 public signature, canonical body, fixture byte, component identity, rule ID, result hash, profile digest, or publication identity.

Every v2 fee evaluation requires both explicit dimensions, with no default or inference:

- execution access route: `DOMESTIC` or `NORTHBOUND_STOCK_CONNECT`;
- fee product class: `ORDINARY_A_SHARE`, `PREFERRED_STOCK`, or `ETF`.

A profile/build-selected `CnAShareFeeExecutionAuthorityV2` is mandatory before reservation or final fee evaluation. It canonically binds a `CnAShareFeeExecutionScopeV2`/hash containing the account, Venue, exact `InstrumentDefinition`/ID/type, CNY quote/settlement currencies, `AUCTION`, permitted Order sides, route/product, and required profile facts. It also binds resolved-profile and composition-request identities, scope-declaration hashes, the exact v2 market/stamp RuleBooks/hashes, and their exact `ProfileComponentRef.component_digest` identities. The two books in one authority are a single selection: no v2 book may be substituted, paired, or reused with another authority by matching route/product alone.

The private Runtime seam is exactly `_create_cn_a_share_fee_execution_authority_v2(resolved_profile, scope, selection, /) -> CnAShareFeeExecutionAuthorityV2 | CnAShareFeeExecutionAuthorityBuildFailureV2`; it owns Profile/Scope/selection support failures. The public binder owns Order account/Venue/Instrument/side/context failures against that scope and never performs a registry lookup. `CnAShareFeeExecutionBindingV2` then binds authority/hash to the exact canonical `Order`/hash, Order ID, account, Venue, Instrument, side, and order-effective instant. Reservation query construction uses only that bound Order; final query construction uses only an exact `Fill`, owns Fill Order/account/Venue/Instrument/side and execution-time failures, and derives effective time only from `Fill.execution_time`. Before any fee-policy lookup, policy canonically re-runs the applicable query constructor and rejects any direct/forged/replace/object-new bypass as `QUERY_PROVENANCE_MISMATCH`; it then owns only remaining authority/query, RuleBook scope, interval, and economic failures. Constructors enforce exact primitive/canonical structure, not hidden semantic fallback. Symbol parsing, current metadata lookup, defaults, nearest-book fallback, and caller-supplied final side or effective time are prohibited.

V2 has new Scope, selection, authority, binding, construction failure, query, policy, RuleBook, Band, resolution, policy failure, reservation-buffer, component, generated-rule, and projection identities. Existing generic `FeeAssessmentPolicy`, `TaxPolicy`, reservation, assessment, Journal, and Ledger contracts are reused unchanged.

Market-fee v2 represents trade-notional charges separately in this order:

1. exchange transaction handling;
2. securities regulatory/management;
3. ChinaClear transfer;
4. HKSCC China Connect transfer.

ChinaClear and HKSCC transfer charges must never be combined into an anonymous `transfer` rate. A charge that does not apply is explicit and produces a not-applicable rule, not an applied zero charge. Stamp duty remains a separate tax policy.

The first enforceable scope is exactly:

```text
execution_access_route: DOMESTIC
fee_product_class: ORDINARY_A_SHARE
venue_id: XSHE
instrument_type: InstrumentType.EQUITY
quote_currency_id: CNY
settlement_currency_id: CNY
trade_mechanism: AUCTION
board_scope: all boards admitted by the bound profile
basis: trade_notional
```

A compatibility projection may copy only finite **XSHE** G08E v1 handling, regulatory, ChinaClear-transfer, and stamp-duty economics into new v2 domestic ordinary-A-share RuleBooks; it rejects any XSHG source Band before constructing output. Every v2 source-ref tuple is nonempty. The projected HKSCC not-applicable charge therefore carries a deterministic compatibility source ref derived from the source RuleBook hashes, XSHE interval, route/product, and charge key. The projection creates only new v2 identities and does not extend the v1 time interval, qualify July 2026, or prove new evidence. `NORTHBOUND_STOCK_CONNECT`, `PREFERRED_STOCK`, and `ETF` require separately evidenced RuleBooks and separately qualifying profile/binding paths; absence is a structured failure, never a fallback to domestic ordinary economics.

Daily portfolio-value fees, clearing instructions, settlement messages, safekeeping, collateral, corporate-action service charges, and other non-trade-notional participant costs are outside execution-fee v2. A future contract must model them using their actual state and basis before any broader cost-coverage claim.

G12H F1 may resume only after the complete additive v2 contract—exact Scope/authority, private profile-binding seam, structured binder/query constructors, and both policies—passes acceptance. That acceptance may use only the finite XSHE v1-to-v2 compatibility projection and does not require G12H evidence, so it is not circular. F1 may then acquire successor-closure evidence only for the enforceable `DOMESTIC + ORDINARY_A_SHARE` scope. F1 closure, F2 projection, F3 publication, and G12H analyzer success remain separate gates; this ADR itself closes none of them.

## Consequences

- G08E/G08H v1 remains byte- and API-identical and continues to fail closed outside its finite evidence.
- The minimal production seam is one additive Kernel fee module plus one private additive Runtime profile-authority binding module; generic Runtime/Kernel code remains A-share-branchless.
- V2 types are public only from the existing concrete A-share profile submodule. `cn_a_share.__all__` preserves every v1 member and order exactly, then appends the v2 names; the global `crypto_quant_trading` and `crypto_quant_backtest` roots remain unchanged. The Runtime profile-binding helper is not a root export.
- Builder, provider, registry, Acceptance Matrix, README, and publication code do not change in the contract slice.
- No provider completeness, July-2026 closure, decision-grade, live, account-statement parity, or deployment claim follows.
