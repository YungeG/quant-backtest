# Binance USDⓈ-M Profile Composition — Primary Sources and Frozen Boundary

## Scope

This note freezes the source/system boundary for G10G. G10G does not introduce a new current-state provider fallback. It composes only caller-supplied immutable G10A–G10F authorities into one development-grade Binance USDⓈ-M profile, generic account-risk evidence, profile registrations, and a profile-neutral financial-dispatcher specification.

G10G does not download Binance data, authenticate, parse provider payloads, build a MarketBundle, reconstruct missing history, mutate a Journal/Ledger, authorize deployment, or claim parity with Binance liquidation or matching-engine behavior. G12 owns acquisition, checksums, revisions, retention, initial state, and completeness. G10H owns first-divergence parity.

## Inherited first-party authorities

G10G inherits, without reinterpretation or fallback:

1. G10A Instrument identity, linear-perpetual type, base/quote/margin currencies, listing interval, and exact `1 base quantity per contract` multiplier.
2. G10B historical price/quantity lattices, notional minimum, admission mode, reduce-only capability, order capabilities, and explicit deferred-rule keys.
3. G10C historical public margin-tier intervals, maximum leverage, maintenance rate/deduction, and finite terminal notional coverage.
4. G10D purpose-specific aggregate-trade and closed mark-price-kline authorities for `EXECUTION_REFERENCE`, `VALUATION`, `MARGIN`, and `LIQUIDATION`.
5. G10E exact Funding Rate History `Regular` publication, associated funding mark, and G09C/G09D settlement evidence.
6. G10F standard-UM one-way/single-asset/cross account mode, selected leverage, account-specific maker/taker commission, fee rules, fee reserve source, and raw `maxNotionalValue`.

Primary source notes remain authoritative:

- `docs/research/binance-usdm-instrument-metadata-primary-sources.md`
- `docs/research/binance-usdm-order-rules-primary-sources.md`
- `docs/research/binance-usdm-margin-tiers-primary-sources.md`
- `docs/research/binance-usdm-price-purpose-streams-primary-sources.md`
- `docs/research/binance-usdm-funding-source-semantics-primary-sources.md`
- `docs/research/binance-usdm-fee-account-profile-primary-sources.md`

## Linear contract composition

The generic G09A `LinearPerpetualContract` is composed only from:

- G10A `InstrumentDefinition` and contract multiplier;
- G10B exact quantity Scale;
- G10B exact price Scale.

`pricePrecision`, `quantityPrecision`, display decimals, mark-price decimals, current filters, or nearby symbols cannot replace the G10B lattices.

## Price-purpose coverage

A successful v1 composition requires exact successful G10D resolutions for:

- `EXECUTION_REFERENCE`;
- `VALUATION`;
- `MARGIN`;
- `LIQUIDATION`.

Funding is supplied separately by G10E and cannot be substituted by a G10D mark. Settlement remains unsupported. Index, estimated settlement, valuation, margin, liquidation, funding, and execution-reference observations remain non-substitutable.

G10B deferred rules are not erased by composition. `PERCENT_PRICE`, `MARKET_TAKE_BOUND`, `TRIGGER_PROTECT`, and advanced order capabilities require semantics not frozen in G10A–G10F and therefore fail G10G v1 composition. `MAX_NUM_ORDERS` and `MAX_NUM_ALGO_ORDERS` require exact historical values and working-order state; a deferred key alone is not a limit.

## Account order-capacity evidence

Binance Exchange Information documents symbol filters `MAX_NUM_ORDERS` and `MAX_NUM_ALGO_ORDERS`. G10B preserved their presence as deferred rule keys but intentionally did not normalize their numeric limits. G10G therefore requires a separate caller-supplied immutable `BinanceUsdmAccountCapacityEvidence` carrying:

- Account and stable Instrument identity;
- finite effective interval and full availability;
- positive `max_num_orders` and `max_num_algo_orders`;
- the exact G10B active-band source key/hash;
- immutable evidence/revision identity.

The generic `AccountRiskPolicy` has one order-capacity dimension rather than separate normal/algo counters. V1 uses `min(max_num_orders, max_num_algo_orders)` as an explicit conservative development convention. It may reject orders Binance would accept; it must never claim the larger category-specific limit is universally available. A later generic split-capacity model can replace this convention only with a new version/digest.

Official source family:

- USDⓈ-M Exchange Information / symbol filters: <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information>

## Exposure-capacity evidence

G10F preserves the selected-leverage `maxNotionalValue` as raw account evidence. G10C supplies finite public tier coverage. G10G maps the account value to exact non-negative USDT Money at Scale 8 and conservatively sets the generic single-currency exposure ceiling to:

```text
min(account maxNotionalValue, G10C finite terminal notional cap)
```

This is an account-risk composition ceiling, not a replacement for G10C tier selection or G09E margin calculation. G09F current exposure and reservation state remain runtime inputs to generic PreTradeRisk. Zero exposure capacity fails closed for opening exposure but may still permit separately proven reduce-only close semantics in a later version; v1 requires a positive ceiling.

Official source families:

- USDⓈ-M Symbol Configuration: <https://developers.binance.com/docs/zh-CN/derivatives/usds-margined-futures/account/rest-api/Symbol-Config>
- Change USDⓈ-M Initial Leverage: <https://developers.binance.com/docs/derivatives/portfolio-margin/account/Change-UM-Initial-Leverage>
- USDⓈ-M Notional and Leverage Brackets: <https://developers.binance.com/docs/derivatives/usds-margined-futures/account/rest-api/Notional-and-Leverage-Brackets>

## Account-risk policy mapping

The composed generic `AccountRiskPolicy` uses:

- Account/Venue from G10F/G10A;
- allowed sides and position effects from the active G10B snapshot;
- reduce-only values from G10B admission mode and reduce-only support;
- fee reserve source `AVAILABLE_MARGIN` from G10F;
- conservative order capacity from capacity evidence;
- conservative USDT exposure ceiling from the G10F/G10C intersection.

`NORMAL` admission may allow ordinary and reduce-only orders when the active rule supports both. `REDUCE_ONLY` permits only `CLOSE` plus `reduce_only=true`. `CLOSED` cannot compose an executable profile. Working-order counts, current exposure, available margin, and reservations are not embedded into the policy; generic PreTradeRisk receives them as point-in-time state.

## Profile component manifest

The market-semantics profile must exact-cover all existing `ProfilePortType` values without adding a Binance-specific generic port. Its digest binds:

- all G10A–G10F model and resolution identities;
- the composed G09A contract;
- the composed AccountRiskPolicy;
- explicit no-tax, no-corporate-action, no-delivery-settlement, and single-USDT-valuation components;
- G09A/G09B position accounting, G09C/G09D funding, G09E/G09F margin, and G09G conservative liquidation identities;
- required price-purpose coverage and remaining limitations.

The simulation profile remains `bar.next_eligible_open.conservative.v1`. Bar-open execution, deterministic slippage, latency, liquidity, mark-to-market closeout, and conservative bar-extreme liquidation audit are repository conventions, not Binance matching-engine facts.

## Registration and dispatch boundary

Frozen registration keys are:

- Market semantics: `crypto.binance_usdm.v1`;
- Simulation: `bar.next_eligible_open.conservative.v1`;
- Execution account: `binance.usdm.standard-cross.v1`.

The previous planning label `binance.usdm.vip0.cross.v1` is rejected because G10F uses account-specific per-symbol commission authority and preserves `feeTier` only as evidence. A fee-tier transition changes the profile digest but does not require a misleading VIP-derived rate key.

G10G produces an immutable `FinancialDispatcherSpec` whose config hash binds the composed contract, risk policy, provider resolutions, component manifests, and development limitations. Engine Cases still contain only the spec and canonical plans/payloads, never the dispatcher implementation object, callback, module path, runtime address, Attempt ID, or wall clock.

## Development limitations

All G10G v1 outputs remain development-only and `deployment_authorized=false` because:

- G12 has not proved complete historical source acquisition/revision coverage;
- bar-open execution and deterministic slippage are not Binance matching-engine parity;
- order capacity is conservatively collapsed from two provider counters to one generic dimension;
- fee rounding lacks Account Trade List parity;
- liquidation is a conservative bar-extreme audit, not Binance liquidation execution;
- settlement, multi-assets, isolated margin, Hedge Mode, BNB discounts, negative rebates, Portfolio Margin, ADL, bankruptcy, insurance-fund, and live behavior remain unsupported.

Changing any source resolution, purpose coverage, capacity evidence, contract, account-risk mapping, component identity, simulation convention, dispatcher spec, or limitation must change the composed profile digest.
