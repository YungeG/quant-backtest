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

The dimensions are bound in one immutable profile/order execution binding before reservation or final fee evaluation. The binding identifies the resolved market profile, execution-account profile, scope declarations, Order, Account, Venue, and Instrument. The fee query must carry that binding and must fail closed if its Order, Account, Instrument, route, or product does not match the selected v2 RuleBook. Symbol parsing, current metadata lookup, defaults, and nearest-book fallback are prohibited.

V2 has new query, policy, RuleBook, Band, resolution, failure, reservation-buffer, component, generated-rule, and projection identities. Existing generic `FeeAssessmentPolicy`, `TaxPolicy`, reservation, assessment, Journal, and Ledger contracts are reused unchanged.

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

A compatibility projection may copy the finite G08E v1 handling, regulatory, ChinaClear-transfer, and stamp-duty economics into new v2 domestic ordinary-A-share RuleBooks. That projection creates only new v2 identities and does not extend the v1 time interval, qualify July 2026, or prove new evidence. `NORTHBOUND_STOCK_CONNECT`, `PREFERRED_STOCK`, and `ETF` require separately evidenced RuleBooks and separately qualifying profile/binding paths; absence is a structured failure, never a fallback to domestic ordinary economics.

Daily portfolio-value fees, clearing instructions, settlement messages, safekeeping, collateral, corporate-action service charges, and other non-trade-notional participant costs are outside execution-fee v2. A future contract must model them using their actual state and basis before any broader cost-coverage claim.

G12H F1 may resume only after the additive v2 contract passes. It may then acquire successor-closure evidence only for the enforceable `DOMESTIC + ORDINARY_A_SHARE` scope. F1 closure, F2 projection, F3 publication, and G12H analyzer success remain separate gates; this ADR itself closes none of them.

## Consequences

- G08E/G08H v1 remains byte- and API-identical and continues to fail closed outside its finite evidence.
- The minimal production seam is one additive Kernel fee module plus one additive Runtime binding module; generic Runtime/Kernel code remains A-share-branchless.
- V2 types are public only from the existing concrete A-share profile submodule. The Runtime binding function is module-public but not exported from the `crypto_quant_backtest` root, preserving the frozen G08H root surface.
- Builder, provider, registry, Acceptance Matrix, README, and publication code do not change in the contract slice.
- No provider completeness, July-2026 closure, decision-grade, live, account-statement parity, or deployment claim follows.
