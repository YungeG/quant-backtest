# Binance USDⓈ-M Instrument Identity and Contract Metadata Primary Sources

## Scope

This note records the first-party facts used to freeze G10A. G10A covers offline normalization of frozen Binance USDⓈ-M `exchangeInfo` evidence into stable internal instrument identity, point-in-time symbols, linear perpetual currency/multiplier metadata, and listing/delisting lifecycle evidence.

It does not cover network collection, MarketBundle construction, tick/step/min-notional rules, margin tiers, price streams, funding, fees, account mode, liquidation execution, live trading, or deployment authorization. Those remain with G10B–G10G and G12.

## Official Binance fields and terminology

Binance USDⓈ-M `GET /fapi/v1/exchangeInfo` documents current symbol records with at least:

- `symbol` and `pair`;
- `contractType`;
- `onboardDate` and `deliveryDate` in epoch milliseconds;
- `status`;
- `baseAsset`, `quoteAsset`, and `marginAsset`;
- precision fields and symbol filters.

The official example uses a USDⓈ-M perpetual record with `contractType="PERPETUAL"`, `status="TRADING"`, stablecoin quote/margin assets, and `deliveryDate=4133404800000`. It explicitly warns that `pricePrecision` is not `tickSize` and `quantityPrecision` is not `stepSize`.

Binance's futures terminology defines:

- `symbol` as the contract symbol name;
- `pair` as the underlying symbol;
- base asset as the asset used for `quantity`;
- quote asset as the asset used for `price`;
- margin asset as the asset used for margin.

It lists USDⓈ-M contract types including `PERPETUAL`, quarterly/monthly delivery contracts, and delivery-only transitional enum values. The G10A union of current/legacy documented contract statuses is exactly `PENDING_TRADING`, `TRADING`, `PRE_DELIVERING`, `DELIVERING`, `DELIVERED`, `PRE_SETTLE`, `SETTLING`, `CLOSE`, `TRADING_HALT`, and `TRADING_CANCEL_ONLY`.

Sources:

- Exchange Information: <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information>
- Legacy Exchange Information snapshot used by searchable official docs: <https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information>
- USDⓈ-M Common Definition: <https://developers.binance.com/docs/derivatives/usds-margined-futures/common-definition>
- Legacy Common Definition: <https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/common-definition>
- New Order endpoint: <https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Order>

## Linear quantity and multiplier convention

The USDⓈ-M schema does not expose the COIN-M `contractSize` field. Binance instead defines the USDⓈ-M base asset as the asset represented by order `quantity`. G10A therefore freezes a provider normalization convention of exactly one base-asset quantity unit per exchange order quantity unit.

This is not permission to derive order lattice or scales from `pricePrecision`/`quantityPrecision`. G10A records the exact rational multiplier only. G10B owns `PRICE_FILTER.tickSize`, `LOT_SIZE.stepSize`, minimum/maximum quantity, minimum notional, and their historical effective intervals. G10G later combines G10A currency/multiplier metadata with G10B numeric scales to construct the G09A `LinearPerpetualContract`.

The COIN-M API is deliberately excluded: its official `exchangeInfo` includes `contractSize`, uses coin margin, and has inverse economics. USDⓈ-M and COIN-M must not share a default based only on endpoint family names.

Sources:

- USDⓈ-M Exchange Information above.
- COIN-M Exchange Information, showing the distinct `contractSize` field: <https://developers.binance.com/docs/derivatives/coin-margined-futures/market-data/rest-api/Exchange-Information>

## Listing and delisting semantics

Binance documents that, after a USDⓈ-M delisting announcement is published, Futures updates `deliveryDate` in `/fapi/v1/exchangeInfo` to the delisting time. The ordinary perpetual example's `4133404800000` date is therefore an open-ended sentinel, not evidence that the contract is genuinely listed until December 2100.

G10A freezes these consequences:

- `onboardDate` is provider listing evidence, not a wall-clock lookup instruction;
- sentinel `deliveryDate=4133404800000` means no finite delisting boundary is supplied by that revision;
- a finite revised `deliveryDate` is a delisting/automatic-settlement boundary only when preserved in a frozen source revision available by the query cutoff;
- status-specific restrictions before automatic settlement, such as reduce-only windows, are historical order-rule evidence and remain with G10B;
- delisting closes the listing interval but does not delete the stable internal `InstrumentId`, historical symbol intervals, or historical Bundle data.

Source:

- Delist Schedule: <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Delist-Schedule>
- Legacy Delist Schedule: <https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/market-data/rest-api/Delist-Schedule>

## Current API data is not historical authority

`/fapi/v1/exchangeInfo` is documented as current exchange trading rules and symbol information; it is not documented as an immutable historical archive. Binance's first-party public-data repository also records `onboardDate` corrections for multiple perpetual symbols. A separate repository issue records a consumer report that live exchange-info endpoints omit expired contracts; G10A treats that report as a retention risk, not as an authoritative API guarantee.

G10A must therefore consume caller-supplied immutable source revisions with `event_time`, `available_at`, revision lineage, source key/hash, and captured-at cutoff. It must never call Binance, read the current API, or reinterpret all history from the latest response.

Sources:

- Binance public-data issue recording corrected `onboardDate` values: <https://github.com/binance/binance-public-data/issues/427>
- Binance public-data consumer report about expired historical contracts: <https://github.com/binance/binance-public-data/issues/162>

## Stable identity and symbol lineage

Binance's documented `symbol`, `pair`, base asset, and quote asset are exchange-facing attributes; none is documented as a permanent cross-rename instrument identifier. Rebranding announcements may delist an old contract and state that a separately announced new contract will be listed.

G10A therefore does not derive stable identity by stripping suffixes, concatenating currencies, trusting `pair`, or matching old/new assets. The caller supplies a canonical stable lineage key backed by frozen source evidence. Revisions may update a symbol interval for that same lineage only when the supplied lineage is explicit and internally consistent. Without such evidence, old and new contracts remain distinct `InstrumentId` values even when a rebranding relationship is known.

This rule prevents survivorship bias and prevents a current symbol from rewriting historical Event IDs, Orders, Fills, Journal entries, or MarketBundle references.

## Frozen G10A system boundary

The smallest sufficient implementation seam is a pure offline profile adapter under `crypto_quant_trading.profiles.binance_usdm`:

- normalized source revision and source-reference values;
- a caller-supplied stable lineage key;
- closed revision-chain selection at `captured_at`;
- exact `PERPETUAL`/USDⓈ-M validation;
- stable `InstrumentDefinition` plus `SymbolTimeline`;
- linear contract metadata containing base/quote/settlement currencies and exact multiplier;
- listing interval and current lifecycle evidence;
- structured failures for missing, late, conflicting, unsupported, or forged evidence.

The adapter does not create a provider client, perform HTTP, parse files, choose a current fallback, infer historical rules from precision fields, or mutate an `InstrumentCatalog`. G12 owns source acquisition and MarketBundle construction.

## Known limitations retained by G10A

- Binance does not supply a documented permanent rename identity in `exchangeInfo`.
- Current `exchangeInfo` is not a complete historical symbol catalog.
- `onboardDate` values have been corrected after publication, so revision provenance is mandatory.
- A finite `deliveryDate` does not by itself encode earlier reduce-only/no-new-position windows.
- `underlyingType`/`underlyingSubType` are descriptive provider fields, not sufficient classification for provider-neutral instrument identity.
- Price/quantity precision fields are not historical order-rule lattices.
- G10A does not authorize USDT=USD valuation, cross-margin behavior, isolated mode, multi-asset mode, fees, funding, liquidation execution, or live deployment.
