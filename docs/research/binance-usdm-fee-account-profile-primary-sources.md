# Binance USDⓈ-M Fee and Account Profile Primary Sources

## Scope

This note records the first-party facts used to freeze G10F. G10F is a pure offline adapter from caller-supplied immutable Binance USDⓈ-M account-configuration snapshots into the existing generic fee-reservation, final-fee, leverage-evidence, and later profile-composition seams.

G10F does not authenticate to Binance, download account data, infer historical settings from current responses, calculate wallet/equity state, reconstruct a missing commission schedule, append Journal entries, execute pre-trade risk, authorize live trading, or prove account-history completeness. G10G owns final Binance profile composition; G12 owns acquisition, encrypted retention, checksums, initial state, all configuration revisions, and complete historical coverage proof.

## Exact per-symbol maker and taker commission

Binance documents a USER_DATA commission-rate endpoint that returns a symbol-specific `makerCommissionRate` and `takerCommissionRate`. Binance also documents that USDⓈ-M sub-account commission is the base commission for the account fee tier plus any symbol-specific commission adjustment. These are stronger account-specific authorities than inferring rates from a public VIP table or from `feeTier` alone.

G10F therefore consumes archived exact per-symbol commission-rate snapshots. `feeTier` is retained as account evidence but never used to synthesize maker or taker rates. Public fee tables and announcements may explain changes, but they do not prove the exact effective rate for one account, symbol, promotion, market-maker program, or commission adjustment.

The accepted v1 rates are non-negative ordinary decimal fractions. Zero is supported. Negative maker rebates are not representable by the existing generic fee rules, whose fee rates are non-negative; liquidity-provider rebate programs therefore fail closed rather than being clipped to zero or recorded as a negative fee.

Sources:

- USDⓈ-M/COIN-M User Commission Rate response shape: <https://developers.binance.com/docs/derivatives/coin-margined-futures/account/rest-api/User-Commission-Rate>
- USDT-M sub-account commission semantics: <https://developers.binance.com/docs/binance_link/exchange-link/fee/Query-Sub-Account-UM-Futures-Commission>
- Example Binance VIP futures fee change with explicit effective schedule: <https://www.binance.com/en/square/post/302815696706097>

## Fee basis, maker/taker role, and fee asset

Binance first-party educational material describes the trading-fee formula as trade notional multiplied by the applicable maker or taker rate. The account trade list exposes per-fill:

- execution price and quantity/quote quantity;
- whether the trade was maker;
- commission amount;
- commission asset;
- trade time and identifiers.

This supports the existing generic per-fill final `FeeAssessmentEngine`: each fill uses its actual notional and liquidity role, then fees are aggregated. Reservation uses the worse of the active maker and taker rates for order notional; final assessment keeps separate maker-only and taker-only account-schedule rules.

For USDⓈ-M contracts, fees are charged in the margin asset, such as USDT for USDT-margined contracts. G10F v1 requires G10A quote and settlement currency, fee currency, and requested reporting currency all to be exact `USDT`. It does not grant a USDT=USDC/BUSD/BNB peg or FX path.

The public sources reviewed show commission amounts with eight fractional digits but do not freeze an exchange-wide rounding algorithm for every product and program. G10F therefore uses an explicit development-only convention: fee reservation rounds upward at USDT Scale 8; final per-fill fee rounds toward zero at USDT Scale 8. G10H must compare the result with archived Account Trade List commission amounts before decision-grade parity is possible.

Sources:

- Binance transaction-fee formula and per-fill guidance: <https://academy.binance.com/en/articles/how-to-calculate-transaction-fees-on-binance>
- USDⓈ-M Account Trade List: <https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/trade/rest-api/Account-Trade-List>

## BNB fee discount is a separate account setting

Binance exposes a separate account-wide USDⓈ-M `feeBurn` setting. `true` enables the BNB fee discount; `false` disables it. Binance also notes in commission-query documentation that commission rates may not reflect the BNB discount.

G10F v1 requires archived `feeBurn=false`. When it is enabled, the final effective rate, fee asset, BNB conversion price, discount version, and exact ordering of discount versus commission calculation are not fully represented by the frozen generic single-currency fee seam. The adapter therefore returns a structured unsupported-mode failure instead of applying a guessed percentage or implicit BNB/USDT conversion.

Sources:

- USDⓈ-M Get BNB Burn Status: <https://developers.binance.com/docs/zh-CN/derivatives/usds-margined-futures/account/rest-api/Get-BNB-Burn-Status>
- USDⓈ-M Toggle BNB Burn: <https://developers.binance.com/docs/derivatives/usds-margined-futures/account/rest-api/Toggle-BNB-Burn-On-Futures-Trade>

## Position mode, asset mode, and cross margin

Binance account configuration exposes:

- `canTrade`;
- `feeTier`;
- `dualSidePosition`;
- `multiAssetsMargin`;
- `tradeGroupId`.

Binance documents `dualSidePosition=true` as Hedge Mode and `false` as One-way Mode. It documents `multiAssetsMargin=true` as Multi-Assets Mode and `false` as Single-Asset Mode.

Symbol configuration and position information expose:

- `marginType`, including `CROSSED`/`cross` and isolated;
- `isAutoAddMargin`;
- selected `leverage`;
- `maxNotionalValue`.

The first Binance development profile is intentionally narrow:

- `canTrade=true`;
- One-way Mode only;
- Single-Asset Mode only;
- crossed margin only;
- automatic isolated-margin addition disabled;
- standard USDⓈ-M account scope, not Portfolio Margin.

Hedge Mode is incompatible with the current signed-net G09A position authority; Multi-Assets Mode requires collateral valuation, haircuts, and FX/asset-index semantics; isolated margin requires separate wallet and liquidation authority. These modes fail closed rather than being treated as aliases of cross single-asset margin.

Sources:

- USDⓈ-M Account Configuration: <https://developers.binance.com/docs/zh-CN/derivatives/usds-margined-futures/account/rest-api/Account-Config>
- USDⓈ-M Current Position Mode: <https://developers.binance.com/docs/derivatives/portfolio-margin/account/Get-UM-Current-Position-Mode>
- USDⓈ-M Current Multi-Assets Mode: <https://developers.binance.com/docs/zh-CN/derivatives/usds-margined-futures/account/rest-api/Get-Current-Multi-Assets-Mode>
- USDⓈ-M Symbol Configuration: <https://developers.binance.com/docs/zh-CN/derivatives/usds-margined-futures/account/rest-api/Symbol-Config>
- USDⓈ-M Position Information V2: <https://developers.binance.com/docs/zh-CN/derivatives/usds-margined-futures/trade/rest-api/Position-Information-V2>

## Selected account leverage

Binance symbol configuration exposes the account's current selected leverage. Binance's leverage-change response also returns the selected leverage and the corresponding maximum notional value. The user-data `ACCOUNT_CONFIG_UPDATE` event carries event time `E`, transaction time `T`, symbol, and new leverage when leverage changes.

G10F maps the archived selected integer leverage directly to the existing generic `LinearMarginLeverageEvidence` with basis `notional_per_initial_margin`. It does not use:

- G10C bracket `ma`, `mi`, or `initialLeverage` as selected account leverage;
- current Symbol Config to backfill an earlier interval;
- `maxNotionalValue` as a replacement for G10C historical tier coverage;
- neighboring symbols or account defaults.

A valid historical book must include an initial symbol-configuration snapshot and every leverage update required to form finite effective intervals. G12 owns that completeness proof.

Sources:

- USDⓈ-M Symbol Configuration: <https://developers.binance.com/docs/zh-CN/derivatives/usds-margined-futures/account/rest-api/Symbol-Config>
- USDⓈ-M Account Configuration Update: <https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams/Event-Account-Configuration-Update-previous-Leverage-Update>
- Change USDⓈ-M Initial Leverage response: <https://developers.binance.com/docs/derivatives/portfolio-margin/account/Change-UM-Initial-Leverage>

## Current endpoints are not historical timelines

The commission, account-config, symbol-config, position-mode, multi-assets-mode, fee-burn, and position-information endpoints describe current USER_DATA state. Most do not provide historical effective intervals. A current response cannot rewrite an earlier backtest or fill a missing account-profile band.

G10F consumes caller-supplied immutable, source-identified bands created from archived endpoint responses and configuration events. Each band carries:

- stable account and G10A Instrument identity;
- finite half-open effective interval;
- full `SimulationInstant` availability;
- raw account, symbol, commission, and fee-burn fields;
- separate source key/hash/revision lineage for each first-party source;
- exact account-scope declaration.

The adapter validates the supplied point-in-time book. G12 must prove that its initial snapshot and all updates are present.

## Frozen generic mappings

One accepted active band produces:

1. `LinearMarginLeverageEvidence` for G09E using the exact selected leverage and effective/available interval;
2. an `AccountFeeScheduleRef` whose digest binds the account, Instrument, maker/taker rates, fee tier, fee-burn state, source revisions, currency, scale, and quantization conventions;
3. a `FeeReservationRuleSet` with explicit market-fee and tax `not_applicable` rules plus one account-schedule order-notional rule at `max(maker,taker)`, rounded upward at USDT Scale 8;
4. a `FinalFeeRuleSet` with explicit market-fee/tax `not_applicable` rules and separate maker-only/taker-only account-schedule per-fill notional rules, rounded toward zero at USDT Scale 8;
5. normalized cross/single-asset/one-way account facts and `FeeReserveFundingSource.AVAILABLE_MARGIN` for later G10G `AccountRiskPolicy` composition.

G10F does not itself create a complete `AccountRiskPolicy`: order-capacity and exposure limits require G10B market rules, G09F current account projection, reservation state, and final G10G capability intersection.

## Exact decimal and identity rules

Commission strings are canonical non-negative ASCII ordinary decimals with at most 18 fractional places. Selected leverage is a positive exact integer. `maxNotionalValue` is retained as raw non-negative decimal evidence but is not interpreted as a margin tier.

Mapping uses string/integer arithmetic only. Raw trailing zeros remain source identity. Float, ambient `Decimal` context, inferred VIP tables, current API fallback, and implicit currency conversion are forbidden.

Any change to account modes, selected leverage, commission rates, fee tier, fee-burn setting, source lineage, effective/available interval, fee currency/scale, or quantization changes the G10F model/resolution identity and must change the composed G10G profile digest.

## Frozen G10F boundary

The smallest sufficient implementation seam is one pure offline module under `crypto_quant_trading.profiles.binance_usdm` that:

- consumes a G10A resolution, account ID, finite caller-supplied historical account-profile book, evaluated/captured instant, and requested reporting currency;
- resolves exactly one visible active standard-account band;
- requires tradable, one-way, single-asset, crossed, no-auto-add, no-BNB-discount, USDT-only semantics;
- maps exact maker/taker rates into matching generic reservation and final fee rule sets;
- maps exact selected leverage into G09E leverage evidence;
- preserves all source, revision, timing, account, mode, fee, currency, scale, and model identities;
- returns structured failures for missing, late, overlapping, conflicting, malformed, unsupported, or forged evidence.

The adapter does not alter generic fee engines, margin model, account-margin projector, pre-trade risk, Journal, Ledger, Engine, Runner, or Timeline behavior.

## Known limitations retained by G10F

- Negative maker rebates and liquidity-provider programs are unsupported by the current non-negative generic fee rules.
- BNB fee discount is unsupported because its effective discount, fee asset, and conversion path are outside the frozen single-USDT seam.
- Hedge, Multi-Assets, isolated, auto-add-margin, and Portfolio Margin modes are unsupported.
- Fee rounding is a development convention pending archived Account Trade List parity.
- Account `feeTier` does not synthesize exact commission rates.
- Current authenticated responses cannot backfill history.
- G10F does not prove wallet, order-count, exposure-capacity, or account-history completeness.
- All output remains development-grade and `decision_grade_eligible=false` until G12 proves immutable account-source retention and G10H proves fee/account parity.
- Direct Binance documentation fetches in the development environment resolve through a fake-IP range and are blocked by SSRF protection; the cited first-party pages were preserved through searchable official content.
