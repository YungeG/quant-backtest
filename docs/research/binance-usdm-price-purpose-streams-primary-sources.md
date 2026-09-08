# Binance USDⓈ-M Historical Price-Purpose Stream Primary Sources

## Scope

This note records the first-party facts used to freeze G10D. G10D covers pure offline normalization of caller-supplied immutable Binance USDⓈ-M historical market-data evidence into purpose-specific generic `MarkObservation` values and provider liquidation-mark bars.

It does not download Binance archives, open WebSocket connections, parse provider JSON/CSV/ZIP files, prove archive completeness, simulate fills, calculate funding, select account state, build a `MarketBundle`, authorize live trading, or fill historical gaps from current APIs. G10G owns runtime composition; G10E owns funding-slot source semantics; G12 owns acquisition, checksums, retention, and complete historical coverage proof.

## First-party historical archives

Binance's official public-data repository states that public market data is published as daily or monthly files. For futures:

- USD-M `aggTrades` files contain the same data as `/fapi/v1/aggTrades`;
- the aggregate-trade columns are aggregate trade ID, price, quantity, first trade ID, last trade ID, timestamp, and buyer-maker flag;
- dedicated scripts download USD-M `markPriceKlines` archives;
- the documented futures-only archive range starts at 2020-01-01;
- checksum files are available.

These facts establish first-party source families, not completeness for a requested run. G12 must retain the exact ZIP/CSV bytes, checksum, path, acquisition time, and gap report used by a run.

Sources:

- Binance public-data README: <https://github.com/binance/binance-public-data/blob/master/README.md>
- Binance public-data downloader README: <https://github.com/binance/binance-public-data/blob/master/python/README.md>
- Binance mark-price-kline downloader: <https://github.com/binance/binance-public-data/blob/5c7f3197/python/download-futures-markPriceKlines.py>
- Binance Data Collection: <https://data.binance.vision/>

## Aggregate trades and execution-reference price

The USDⓈ-M aggregate-trade stream documents:

- `E`: event time;
- `a`: aggregate trade ID;
- `p`: price;
- `q`: quantity;
- `f`/`l`: first and last trade IDs;
- `T`: trade time;
- `m`: whether the buyer is the maker.

Aggregate trades are market trades aggregated for a single taker order. G10D maps the exact `p` price at `T` to `PricePurpose.EXECUTION_REFERENCE`. It does not claim that this observation is itself a simulated fill, bar-open event, best bid/ask, or order-book execution. G10G may use the separately preserved aggregate-trade event and availability evidence when composing execution behavior.

A contract kline's opening price is not used as an immediately available execution reference at the bucket boundary: the opening price is only known after the first underlying trade has occurred. Mapping the final archived kline open to the scheduled bucket start would introduce lookahead under the current `BarOpenObservation` contract. Book ticker is also not substituted in G10D v1 because it is quote evidence, not a completed trade, and execution/queue semantics remain outside this gate.

Source:

- USDⓈ-M Aggregate Trade Streams: <https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Aggregate-Trade-Streams>

## Mark-price stream fields

The official USDⓈ-M Mark Price Stream publishes a mark-price update every three seconds or one second. Its documented payload includes:

- `E`: event time;
- `s`: symbol;
- `p`: mark price;
- `ap`: mark-price moving average;
- `i`: index price;
- `P`: estimated settlement price, useful only in the final hour before settlement;
- `r`: funding rate;
- `T`: next funding time;
- `st`: symbol type after UM/CM integration.

The fields are distinct authorities. G10D never treats `i`, `P`, `ap`, or a contract trade price as aliases for `p`.

Source:

- USDⓈ-M Mark Price Stream: <https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/websocket-market-streams/Mark-Price-Stream>

## Mark-price klines

The official USDⓈ-M Mark Price Kline endpoint describes its rows as candlestick bars for a symbol's mark price and states that rows are uniquely identified by open time. The documented row contains:

- open time;
- open, high, low, and close mark prices;
- close time;
- ignored/non-economic fields.

The close field is described as the close, or the latest price while a bar is still open. Therefore only a caller-declared closed historical bar may authorize a final close observation or liquidation range. An in-progress row must not be frozen as final historical OHLC evidence.

G10D maps one accepted closed mark-price-kline row into separate purpose-specific evidence:

- close → `PricePurpose.VALUATION`;
- close → `PricePurpose.MARGIN`;
- close plus low/high → `PricePurpose.LIQUIDATION` point/bar evidence.

The source row may be shared, but each normalized output has its own purpose-specific stream identity. Generic consumers may not fall back across those streams.

Source:

- USDⓈ-M Mark Price Kline/Candlestick Data: <https://developers.binance.com/docs/zh-CN/derivatives/usds-margined-futures/market-data/rest-api/Mark-Price-Kline-Candlestick-Data>

## Margin and liquidation authority

Binance's USDⓈ-M common definitions state that mark price is used for market-order minimum-notional evaluation. Binance's order documentation also distinguishes `MARK_PRICE` from `CONTRACT_PRICE` as separate trigger working types. Account and position examples expose mark price alongside unrealized profit, maintenance margin, and liquidation price. These first-party contracts support retaining mark price as the Binance risk-purpose source rather than substituting last trade or ordinary contract-kline close.

G10D does not reproduce Binance's account liquidation engine. It only maps archived mark-price ranges to the provider-neutral conservative liquidation-audit input later composed by G10G.

Sources:

- USDⓈ-M Common Definition: <https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/common-definition>
- USDⓈ-M conditional-order working type and mark-price triggers: <https://developers.binance.com/docs/derivatives/portfolio-margin/trade/New-UM-Conditional-Order>

## Settlement price is not available from the accepted v1 sources

The Mark Price endpoint and stream label `P` as an **estimated** settlement price and say it is useful only in the final hour before settlement. It is not documented as the final automatic-settlement price.

Binance delisting announcements establish an automatic-settlement time for expiring or delisted perpetual contracts, but the public market-data pages reviewed for G10D do not provide an immutable historical final-settlement-price stream with sufficient event, availability, revision, and source lineage for the generic `PricePurpose.SETTLEMENT` contract.

G10D v1 therefore owns an explicit fail-closed settlement mapping:

- `P` must not map to `PricePurpose.SETTLEMENT`;
- index-price klines must not map to `PricePurpose.SETTLEMENT`;
- mark-price close or aggregate-trade price must not map to `PricePurpose.SETTLEMENT`;
- a settlement query returns a structured unsupported-purpose failure until a first-party final-settlement source contract is separately frozen.

Sources:

- USDⓈ-M Mark Price REST response: <https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/market-data/rest-api/Mark-Price>
- Example USDⓈ-M automatic-settlement/delisting announcement: <https://www.binance.com/en/square/post/7809671247033>

## Funding-time mark remains G10E-owned

Binance's Funding Rate History response includes `fundingTime`, `fundingRate`, and the mark price associated with a particular funding-fee charge. That source is the correct first-party candidate for the exact funding-slot mark, but its publication, slot identity, revisions, rate semantics, and eligibility relationship belong to G10E.

G10D must not manufacture `PricePurpose.FUNDING` from a nearby mark-price-kline close or ordinary mark update. A G10D funding query fails with a structured purpose-owned-by-G10E result.

Source:

- USDⓈ-M Funding Rate History: <https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History>

## Event, observation, close, and availability time

G10D freezes four different timing concepts:

1. aggregate-trade observation time is provider trade time `T`;
2. mark-price-kline interval start is provider open time;
3. final close observation time is provider close time, while the liquidation interval end-exclusive is close time plus one millisecond;
4. availability is separate caller-supplied immutable archive/replay evidence and must not precede the source fact becoming knowable.

For aggregate trades, `available_at >= trade_time`. For a final mark-price bar, `closed_at.instant` equals interval end-exclusive and `available_at >= closed_at`. If knowledge becomes available later only by `SimulationInstant.phase` or `source_sequence` while sharing the same UTC nanosecond, the current generic `MarkObservation.available_at: UtcInstant` cannot represent that ordering. G10D fails closed instead of erasing the distinction.

`captured_at` controls which archived source revision is visible. It is not replaced by current API time, filesystem modification time, or run wall clock.

## Exact decimal and source identity rules

All accepted source prices and quantities remain canonical ordinary decimal strings in provider evidence. Mapping uses integer/string arithmetic only, with no float or ambient `Decimal` context. Trailing zeros remain part of source identity; behavior uses the smallest exact common scale required by each mapped price set, up to the repository's maximum supported scale.

Every normalized event retains:

- stable G10A instrument identity;
- provider natural event ID;
- source key and SHA-256 content hash;
- source revision ID and optional superseded revision;
- raw provider timestamps and decimal strings;
- separate observed/closed and available times;
- purpose-specific stream ID.

Changing any purpose-to-source mapping changes the G10D model digest and therefore must change the composed G10G profile digest.

## Coverage, gaps, and staleness

Coverage is declared and checked separately for every purpose-specific stream. A valid G10D historical price book has finite half-open coverage, no overlapping source bands, no cross-instrument rows, no duplicate visible natural event IDs, and no current/latest fallback.

G10D validates only the caller-declared source coverage and row/source consistency. It does not prove that Binance published every expected row or that every public archive file was retained. G12 owns that stronger completeness proof.

Point-price selection delegates to the existing provider-neutral `MarkResolver`, so availability, ambiguity, forward-fill, and maximum-age behavior remain purpose-specific through `StaleMarkPolicy`. Liquidation OHLC coverage is validated independently and is never replaced by point-price forward fill.

## Frozen G10D boundary

The smallest sufficient implementation seam is a pure offline module under `crypto_quant_trading.profiles.binance_usdm` that:

- consumes a G10A resolution plus caller-supplied immutable aggregate-trade and closed mark-price-kline evidence;
- maps aggregate-trade price only to execution-reference observations;
- maps mark-price-kline close separately to valuation, margin, and liquidation observations, and low/high to liquidation bars;
- keeps settlement unsupported and funding G10E-owned;
- preserves exact timing, decimal, revision, source, and purpose-specific stream identity;
- delegates point selection/staleness to generic `MarkResolver` without adding Binance branches;
- emits development-grade provider resolution evidence and structured failures for missing, late, overlapping, malformed, conflicting, unsupported, or unrepresentable evidence.

The adapter does not alter generic Engine, Runner, Ledger, Snapshot, Margin, liquidation audit, or execution models.

## Known limitations retained by G10D

- Binance's public archive provides `aggTrades` and `markPriceKlines`, not a documented immutable final-settlement-price archive.
- Public archive presence is not proof of gap-free completeness; G12 remains required.
- Final mark-price-kline OHLC has bar resolution and cannot reconstruct intrabar mark path.
- Same-UTC phase/sequence-only availability cannot be represented by current generic point marks and is rejected.
- Aggregate-trade price is a reference observation, not a fill or order-book simulation.
- Funding-time mark, source publication, and slot semantics remain G10E-owned.
- All G10D output remains development-grade and `decision_grade_eligible=false` until G12 proves source retention and completeness.
- Direct page fetches in the development environment resolve through a fake-IP range and are blocked by SSRF protection; the cited first-party pages were preserved through searchable official content and exact passage retrieval where available.
