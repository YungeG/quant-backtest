# Binance USDⓈ-M Historical Margin and Leverage Tier Primary Sources

## Scope

This note records the first-party facts used to freeze G10C. G10C covers pure offline normalization of caller-supplied immutable Binance USDⓈ-M bracket-update evidence into the generic G09E historical margin rule contract.

It does not acquire or replay Binance streams, call authenticated account APIs, choose account leverage, calculate account equity, model isolated/multi-asset/portfolio margin, execute liquidation, build a MarketBundle, authorize live trading, or establish decision-grade historical completeness. G10F owns account leverage/mode evidence; G12 owns acquisition, archival retention, and coverage proof.

## Historical bracket update evidence

Binance's official USDⓈ-M Contract Info Stream states that symbol status changes are pushed for listing, settlement, and bracket adjustment; `bks` appears only when a bracket is updated. The documented bracket payload contains:

- `bs`: bracket level;
- `bnf`: floor notional;
- `bnc`: cap notional;
- `mmr`: maintenance margin ratio;
- `cf`: quick-calculation auxiliary amount;
- `mi`: lower edge of the displayed leverage range;
- `ma`: upper edge of the displayed leverage range.

The event also contains `E`, the event time, and `s`, the exchange symbol. G10C treats an archived bracket-update event as a source revision only when the caller supplies its stable G10A instrument lineage, exact event/effective instant, separate availability instant, source key/hash, revision lineage, and finite declared coverage. A status-only Contract Info event without `bks` cannot create or replace a margin tier revision.

Source:

- USDⓈ-M Contract Info Stream: <https://developers.binance.com/docs/zh-CN/derivatives/usds-margined-futures/websocket-market-streams/Contract-Info-Stream>

## Binance maintenance formula and `cf`/`cum`

Binance's USDⓈ-M leverage and margin guidance states:

`Maintenance Margin = Notional Position Value × Maintenance Margin Rate - Maintenance Amount`

Binance's Portfolio Margin explanation gives the equivalent USDⓈ-M formula:

`futuresMM_USDⓈ-M = |MMR × Position × MarkPrice| - cum`

and identifies `cum` as the Maintenance Amount from the Futures leverage and margin rules. G10C therefore maps the Contract Info `cf` quick-calculation amount to generic G09E `maintenance_margin_deduction`, preserving the exact provider value rather than recomputing it from rounded rates.

Sources:

- Leverage and Margin of USDⓈ-M Futures: <https://www.binance.com/my-MM/support/faq/detail/360033162192>
- Unified Maintenance Margin Ratio calculation: <https://www.binance.com/it/support/faq/detail/4868b2f1aa6c4d08af973328462bb0bd>

## Boundary convention and finite terminal cap

Binance's official tier-adjustment announcements publish bracket tables using upper-inclusive intervals, for example:

- `0 < Position ≤ 5,000`;
- `5,000 < Position ≤ 25,000`;
- a finite final bracket such as `3,000,000 < Position ≤ 3,500,000`.

The final published cap is therefore not an unbounded continuation. Mapping it to `None` would erase a provider position limit and could admit unsupported notional. Mapping equality at a shared boundary to the next bracket would also be wrong for maximum-leverage validation.

G10C requires a backward-compatible provider-neutral G09E extension:

- rule intervals explicitly declare their tier boundary convention;
- existing synthetic rules retain lower-inclusive/upper-exclusive behavior;
- Binance rules use first-tier-zero-or-positive, then lower-exclusive/upper-inclusive selection;
- a finite terminal cap is valid coverage;
- notional above a finite terminal cap returns a structured outside-tier-coverage failure instead of assertion, fallback, or an invented unbounded tier.

Source:

- Binance Futures tier adjustment announcement with before/after tables: <https://www.binance.com/en/square/post/7809671247033>

## Exact field mapping

For an accepted archived Contract Info bracket revision, G10C maps:

| Binance evidence | Generic G09E authority |
| --- | --- |
| `bs` | stable provider bracket identity within the source revision |
| `bnf` | settlement-currency exact `notional_floor` |
| `bnc` | settlement-currency exact finite `notional_cap` |
| `ma` | `maximum_leverage` with basis `notional_per_initial_margin` |
| `mmr` | `maintenance_margin_rate` with basis `maintenance_margin_fraction_of_notional` |
| `cf` | nonnegative `maintenance_margin_deduction` |
| event/effective instant | `LinearMarginRuleInterval.effective_from` |
| next visible accepted revision | prior interval `effective_to_exclusive` |
| caller capture evidence | interval `available_at` and source provenance |

`mi` is preserved in provider source identity and golden evidence but is not mapped as a minimum selectable account leverage. The tier's economic limit used by G09E is `ma`; selected account leverage remains separate `LinearMarginLeverageEvidence` owned by G10F.

All numeric source values are canonical ordinary decimal strings and are converted with integer/string arithmetic only. G10C does not use float, ambient `Decimal` context, `pricePrecision`, `quantityPrecision`, or current endpoint values.

## `initialLeverage` and selected account leverage

The authenticated leverage-bracket response names `initialLeverage` as the maximum leverage for a bracket. This corresponds to Contract Info `ma` and maps to generic `maximum_leverage`; it does not become `LinearMarginLeverageEvidence`.

Changing or querying a user's selected initial leverage is account configuration. G10F must provide point-in-time account-scoped leverage evidence with its own effective/available/source identity. G10C must not infer selected leverage from a bracket's maximum.

Sources:

- USDⓈ-M Notional and Leverage Brackets endpoint: <https://developers.binance.com/docs/derivatives/usds-margined-futures/account/rest-api/Notional-and-Leverage-Brackets>
- Account Configuration Update (Leverage Update): <https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams/Event-Account-Configuration-Update-previous-Leverage-Update>

## `notionalCoef` is account-scoped and unsupported in G10C v1

Binance's authenticated UM leverage-bracket example includes `notionalCoef` alongside symbol brackets. The field is absent from the public Contract Info bracket-update payload. The authenticated endpoint is `USER_DATA`, does not provide a historical revision timeline, and the UM page does not define a safe historical transformation that G10C can apply independently of account identity.

G10C v1 therefore accepts only default symbol-time bracket revisions derived from archived Contract Info bracket updates. Any normalized source carrying `notionalCoef`, or otherwise declared account-adjusted, fails with a structured account-adjusted-tier-unsupported result. G10C never multiplies floors/caps a second time and never shares account-adjusted tiers across accounts. Account-specific bracket policy may be added with G10F/G12 only after account identity, effective time, availability, and transformation semantics are frozen.

Source:

- UM Notional and Leverage Brackets (`USER_DATA`) example: <https://developers.binance.com/docs/zh-CN/derivatives/portfolio-margin/account/UM-Notional-and-Leverage-Brackets>

## Current endpoints are not historical authority

The authenticated leverage-bracket endpoints return account-visible current configuration; they do not document immutable historical replay. Binance announcements also show that leverage/margin tiers change at dated instants and may affect existing positions. G10C must not apply a current response to an earlier interval or use it to fill a missing archived update.

A valid G10C rule book therefore requires:

- caller-supplied immutable revisions;
- stable G10A instrument identity rather than symbol-derived identity;
- explicit effective and available instants;
- closed revision lineage and canonical source hashes;
- finite declared coverage with no current/latest fallback;
- unique visible revision selection by `captured_at`;
- exact contiguous tier geometry and explicit boundary convention.

G12 must prove that the archive contains the state effective at coverage start plus every relevant bracket update through coverage end. Without that proof, G10C output remains development-grade.

## Frozen G10C boundary

The smallest sufficient implementation seam is a pure offline module under `crypto_quant_trading.profiles.binance_usdm` that:

- consumes a G10A resolution plus an immutable historical margin tier rule book;
- selects only evidence visible by `captured_at`;
- validates finite time coverage, revision/source lineage, exact decimal grammar, bracket order/contiguity, upper-inclusive boundary semantics, finite terminal cap, leverage/rate/deduction bases, and source context;
- emits generic `LinearMarginRuleBook`/`LinearMarginRuleInterval`/`LinearMarginTier` authority plus provider resolution evidence;
- preserves raw `bs/bnf/bnc/mmr/cf/mi/ma` values and source hashes;
- structured-fails missing, late, overlapping, account-adjusted, malformed, conflicting, or forged evidence.

The adapter does not create `LinearMarginLeverageEvidence`, call G09E margin evaluation, read marks, query positions/wallets, or compose a runtime profile.

## Known limitations retained by G10C

- Binance documents a real-time update stream, not a public historical replay service; archive completeness belongs to G12.
- An initial bracket state before the requested coverage start must already exist in caller evidence.
- Announcement tables corroborate boundaries and changes but do not always expose `cf`/Maintenance Amount, so they are not sufficient alone for the v1 normalized tier payload.
- `notionalCoef` account-adjusted history is unsupported.
- Selected leverage, margin mode, hedge/one-way mode, multi-asset behavior, portfolio collateral, wallet equity, liquidation execution, fees, and funding are outside G10C.
- Direct page fetches in the development environment resolve through a fake-IP range and are blocked by SSRF protection; the cited first-party pages were preserved through searchable official content and exact passage retrieval where available.
