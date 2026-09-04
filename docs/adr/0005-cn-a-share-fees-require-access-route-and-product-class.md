# ADR 0005: China A-share Execution Fees Require Access Route and Product Class

- Status: Accepted
- Date: 2026-08-19
- Scope: G08E v2, G12H

## Context

G08E v1 uses a route- and product-blind `CnAShareCashFeeRuleQuery`. That finite August-2023 authority is valid only under its domestic ordinary-A-share caller precondition. G12H established that one reusable fee RuleBook is false across Northbound ordinary shares, preferred stock, and ETFs: Northbound has a separate HKSCC trade-notional transfer charge, preferred handling differs, and ETF handling/waivers differ.

`InstrumentType.EQUITY`, symbol text, stable key, board, account permission, or current metadata cannot infer the selected execution route or fee product. Non-notional portfolio, instruction, and settlement costs require other state/bases and cannot be blended into a trade-notional rate.

## Decision

Add an additive execution-fee v2 domain contract. Preserve every G08E/G08H v1 signature, canonical body/hash, fixture byte, component identity, profile digest, publication identity, root export, and finite fail-closed behavior.

Every v2 fee evaluation requires explicit, immutable values with no default or inference:

- access route: `DOMESTIC` or `NORTHBOUND_STOCK_CONNECT`;
- fee product class: `ORDINARY_A_SHARE`, `PREFERRED_STOCK`, or `ETF`.

A v2 execution scope/authority binds the selected route/product with the exact account, Venue, Instrument, CNY/AUCTION context, selected v2 market/stamp RuleBooks, and component identities. Reservation is bound to an exact Order; final assessment is bound to an exact Fill and its execution time. Missing or inconsistent scope, Order, Fill, route, product, or RuleBook fails closed. ChinaClear and HKSCC are always separate charge identities. A non-applicable charge remains an explicit not-applicable rule, never an applied zero charge.

The first compatible economics are only finite `DOMESTIC + ORDINARY_A_SHARE + XSHE` v1-to-v2 projection. It rejects XSHG before output construction, has nonempty deterministic provenance for HKSCC not-applicability, does not extend an interval, and does not prove July-2026 authority. Northbound, preferred, and ETF books require separate evidence.

Runtime profile/order selection, additive profile/build identity, Semantic Run integration, and final acceptance are separate work. They are decomposed in the [v2 roadmap](../implementation/plans/g08/g08e-route-product-fee-v2.md): V2A pure Kernel first, V2B Runtime binding after V2A passes, then V2C acceptance. This ADR intentionally freezes no Runtime helper signature, profile/build leaf preimage, registration field, or Semantic Run field.

Daily portfolio-value fees, clearing instructions, settlement messages, safekeeping, collateral, corporate-action service charges, and other non-trade-notional participant costs are outside execution-fee v2.

## Consequences

- Generic `FeeAssessmentPolicy`, `TaxPolicy`, reservation, assessment, Journal, and Ledger seams remain reused; no second fee engine or generic route/product framework is introduced.
- V2 Kernel names append only to the concrete A-share submodule; global roots remain unchanged.
- V2C acceptance is `PASSED`; G12H F1 may acquire predecessor/endpoint/successor evidence only for execution-enforced `DOMESTIC + ORDINARY_A_SHARE`.
- This decision claims no provider completeness, July-2026 closure, decision grade, live use, deployment, or full cost coverage.
