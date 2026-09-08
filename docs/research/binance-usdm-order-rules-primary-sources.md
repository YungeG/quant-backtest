# Binance USDⓈ-M Historical Order Rules Primary Sources

## Scope

This note records the first-party facts used to freeze G10B. G10B is a pure offline adapter from caller-supplied historical USDⓈ-M rule intervals to generic `OrderRuleTimeline`, execution-style quantity lattices, and order capabilities.

It covers static `PRICE_FILTER`, `LOT_SIZE`, `MARKET_LOT_SIZE`, `MIN_NOTIONAL`, provider order-type/TIF declarations, and explicit normal/reduce-only/closed admission intervals. It does not collect data, call Binance, infer missing history from the current API, resolve mark-relative `PERCENT_PRICE`, enforce account-mode compatibility, count open/algo orders, model wire parameters, or simulate fills.

## Current exchange information is not historical authority

Binance describes `GET /fapi/v1/exchangeInfo` as **current exchange trading rules and symbol information**. Binance tick-size announcements state that the API value changes at the adjustment time and instruct clients to query `/fapi/v1/exchangeInfo` for the current/latest tick size. The same announcements state that existing orders continue matching with their original tick size after the update.

Consequences frozen by G10B:

- the latest response cannot be applied backward across a backtest;
- caller-supplied immutable half-open rule intervals require source key/hash and `available_at` provenance;
- a newly admitted order uses the unique interval effective at admission;
- an already accepted order retains its original MarketRuleDecision/rule identity and is not retroactively re-admitted under a later tick;
- gaps, overlaps, late-only evidence, and current-rule fallback fail closed.

Sources:

- USDⓈ-M Exchange Information: <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information>
- Official USDⓈ-M tick-size adjustment example: <https://www.binance.com/en/square/post/304683457551986>
- Additional official adjustment example with temporary suspension: <https://www.binance.com/en/square/post/329984678922482>

## `PRICE_FILTER`

The official USDⓈ-M common definition states:

- `minPrice` is the minimum allowed `price`/`stopPrice`, disabled when zero;
- `maxPrice` is the maximum allowed `price`/`stopPrice`, disabled when zero;
- `tickSize` is the allowed price interval, disabled when zero;
- enabled values must satisfy the lower bound, upper bound, and tick lattice.

G10B parses provider decimal strings with integer/string arithmetic only. It preserves the raw strings in source evidence, derives the smallest exact common `Scale`, and never uses `pricePrecision`. The existing generic evaluator uses a zero-origin tick lattice, so G10B qualifies only filter geometry where every enabled `minPrice` lies on the tick lattice. Any geometry that would require an unrepresented offset fails closed instead of being rounded or approximated.

Source:

- USDⓈ-M Common Definition: <https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/common-definition>

## `LOT_SIZE` and `MARKET_LOT_SIZE`

Binance defines `LOT_SIZE` for ordinary order `quantity` and `MARKET_LOT_SIZE` specifically for `MARKET` order quantity. Each has independent `minQty`, `maxQty`, and `stepSize`, with minimum, maximum, and step-lattice checks.

The two filters can differ. The official USDⓈ-M exchange-info example shows a larger `LOT_SIZE.maxQty` than `MARKET_LOT_SIZE.maxQty`. G10B must therefore not collapse both into one lattice.

G10B freezes a backward-compatible generic `OrderRuleSnapshot.market_quantity_lattice` extension:

- `LIMIT` and `STOP_LIMIT` use the existing primary quantity lattice and limit quantity cap;
- `MARKET` and `STOP` use the optional market quantity lattice and market quantity cap;
- snapshots without the optional lattice retain their existing canonical schema and hashes;
- Binance bands normalize both lattices to one exact quantity Scale so the same Instrument can carry either order style without float conversion.

Sources:

- USDⓈ-M Common Definition above.
- USDⓈ-M Exchange Information example above.

## `MIN_NOTIONAL`

Binance defines USDⓈ-M `MIN_NOTIONAL` as the minimum `price × quantity` value. For `MARKET` orders, which have no supplied order price, Binance uses mark price.

G10B stores the exact minimum as quote-currency `Money` at a scale sufficient for exact price-times-quantity arithmetic. It does not fetch or choose a mark. A later G10D/G10G composition must supply an eligible mark-price `OrderRuleNotionalEvidence` for Market/Stop admission; a trade close, bar close, valuation price, or current API value cannot silently replace it.

Source:

- USDⓈ-M Common Definition above.

## Order types and time in force

The official USDⓈ-M definitions list provider order types including `LIMIT`, `MARKET`, `STOP`, `STOP_MARKET`, `TAKE_PROFIT`, `TAKE_PROFIT_MARKET`, and `TRAILING_STOP_MARKET`. Documented TIF values include `GTC`, `IOC`, `FOK`, `GTX`, and in newer definitions `GTD`/`RPI`.

The generic v1 domain represents Market, Limit, Stop-Market-like, and Stop-Limit-like styles, but it does not represent every Binance trigger direction, trailing callback, `goodTillDate`, RPI eligibility, price-match mode, STP mode, or close-all wire combination. G10B therefore:

- requires `LIMIT` and `MARKET` source capability;
- maps Limit TIF only through the exact generic intersection `GTC`/`IOC`/`FOK`/`GTX`;
- represents Market as `PriceConstraintShape.NONE` plus generic `TimeInForce.IOC` immediate non-resting semantics and leaves provider wire-field omission to later translation;
- preserves known but unmodeled order/TIF features as explicit deferred rule keys;
- rejects unknown provider values rather than silently treating them as supported.

Sources:

- USDⓈ-M Common Definition above.
- USDⓈ-M New Order: <https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Order>
- Legacy USDⓈ-M New Order: <https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/trade/rest-api>

## Reduce-only and admission state

Binance's New Order documentation states that `reduceOnly` cannot be sent in Hedge Mode and cannot be combined with close-all `closePosition`. Error definitions also expose symbol/account reduce-only restrictions. Delisting announcements commonly establish a time before settlement after which users may not open new positions but may still reduce existing positions.

G10B therefore separates symbol-time admission evidence from account mode:

- `NORMAL` allows ordinary OPEN/CLOSE/AUTO admission;
- `REDUCE_ONLY` allows only `PositionEffect.CLOSE` and requires `reduce_only=true`;
- `CLOSED` rejects new admission;
- a non-tradable G10A metadata status also closes admission;
- G10F must later intersect this symbol capability with one-way/hedge account mode and account restrictions.

G10B never infers a historical reduce-only interval from a current status string or generic delisting habit. The interval must be caller-supplied frozen evidence.

Sources:

- USDⓈ-M New Order above.
- USDⓈ-M Error Codes: <https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/error-code>
- Delist Schedule: <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Delist-Schedule>

## Temporary suspension during rule changes

Official tick-size announcements may specify a short trading suspension during which users cannot place, cancel, or modify orders, and the contract status changes from `TRADING` to `PENDING_TRADING`. Other tick changes occur without a trading suspension.

G10B binds the G10A point-in-time metadata resolution. A non-tradable active metadata status produces a suspended generic snapshot, while the historical tick interval still changes at its declared boundary. The adapter cannot infer suspension merely because a tick changed.

Source:

- Official adjustment examples above.

## Deferred filters and later ownership

USDⓈ-M exchange information also carries rules that the frozen G10B static seam cannot fully evaluate alone:

- `PERCENT_PRICE` depends on mark price and belongs to G10D/G10G composition;
- `MAX_NUM_ORDERS` and `MAX_NUM_ALGO_ORDERS` depend on account working-order state and belong to later account/pretrade composition;
- `marketTakeBound` is execution-price behavior, not a static quantity/price admission lattice;
- `triggerProtect`, price-match, STP, GTD/RPI, trailing-stop, and close-all combinations need additional generic semantics or translation/account evidence.

A normalized G10B band must declare all known deferred keys. Resolution retains them and remains `decision_grade_eligible=false` while any unresolved key exists. Unknown keys fail closed. This prevents the source hash from hiding silently ignored provider rules.

## Frozen G10B seam

The smallest sufficient seam is `crypto_quant_trading.profiles.binance_usdm.order_rules`:

- source ref;
- immutable half-open rule band;
- finite rule book with declared coverage;
- query bound to a G10A metadata resolution, session, economic instant, and captured-at cutoff;
- pure resolver returning generic timeline, active snapshot, independent limit/market lattices, capability set, active source band, and deferred-rule evidence;
- structured failures for missing, late, gapped, overlapping, malformed, unsupported, or forged evidence.

No HTTP client, JSON/file parser, current-rule fallback, provider SDK, wall clock, MarketBundle access, account lookup, mark lookup, Engine branch, or deployment authorization belongs in G10B.
