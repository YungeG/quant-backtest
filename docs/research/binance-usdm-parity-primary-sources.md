# Binance USDⓈ-M Parity — Primary Sources and Frozen Boundary

## Scope

This note defines the evidence boundary for G10H. G10H is parity tooling, not a second exchange simulator and not a provider-data acquisition gate. It compares the frozen G10G development journey against:

1. the immutable `crypt-gemini` Source Snapshot already frozen by WP-00C; and
2. caller-supplied immutable Binance account evidence when a parity case includes actual exchange observations.

G10H may normalize evidence and report the first semantic divergence. It must not query Binance, read secrets, fill historical gaps with current endpoints, rewrite G10A–G10G authority, add a Binance branch to generic Runtime code, or authorize deployment. G12 owns acquisition, retention, checksums, revision history, initial state, and completeness proof.

A G10H gate can pass while a parity case has verdict `MISMATCH`, `APPROVED_CHANGE`, or `NOT_COMPARABLE`. Gate success means the comparator truthfully classified the evidence; it does not mean Binance matching-engine parity was achieved.

## Frozen `crypt-gemini` authority

WP-00C freezes this source identity:

- Source ID: `crypt-gemini`;
- Snapshot ID: `sha256:d6e6feca46b61586e890a441443738dc9e911a58428c940e86055459361eda80`;
- archive SHA-256: `d6e6feca46b61586e890a441443738dc9e911a58428c940e86055459361eda80`;
- content-tree SHA-256: `704dee87020ad119e417fbec3831875f8203787ba06206f625a07e2414a068bb`;
- provenance base commit: `ba36e8a2b9ca1b1a949cf71cc93e175c9ef5e014`;
- frozen worktree state: `dirty`.

Authoritative manifest:

- `tests/parity/fixtures/legacy-sources/crypt-gemini-d6e6feca46b61586e890a441443738dc9e911a58428c940e86055459361eda80.manifest.json`

The dirty source worktree is provenance, not identity. The content-addressed archive and manifest are the only legacy source authority.

### What the snapshot actually models

The overlapping execution path is primarily:

- `research/hummingbot_audited/contracts.py`;
- `research/hummingbot_audited/engine.py`;
- `research/hummingbot_audited/result.py`;
- `research/blend_v2/execution.py`.

The frozen code provides:

- action and order traces;
- next-known-open execution;
- quantity/rule validation;
- a long-position state machine;
- deterministic fee and slippage rates supplied by the request;
- funding entries calculated from frozen funding rows;
- quote-ledger, PnL, position snapshots, and reconciliation summaries.

The legacy `OrderTrace` stores executor, timestamp, event, optional base amount/reference price, and textual details. The engine opens a `CausalLongRequest` at the next eligible open, calculates margin as notional divided by requested leverage, and emits `OPEN`, `SCHEDULE_EXIT`, `LEVERAGE`, and `CLOSE` traces. The `blend_v2` funding path applies `-target_exposure × funding_rate`, while fee/slippage use fixed caller-supplied rates.

### What the snapshot cannot prove

The frozen snapshot is not a Binance matching-engine or account-history oracle. It does not preserve actual Binance:

- Account Trade IDs, Order IDs, maker/taker classification, commissions, or realized-PnL rows;
- partial-fill sequence or queue position;
- order-book liquidity, latency, STP, price-match, GTD, or exchange rejection sequence;
- One-way short/flip behavior equivalent to the G10G journey;
- account wallet, working-order, maintenance-margin, or liquidation-engine state;
- force-order, ADL, bankruptcy, or insurance-fund execution;
- provider archive completeness.

Therefore G10H must compare only overlapping semantics to `crypt-gemini`. Non-overlapping behavior is `NOT_COMPARABLE` or an ADR-backed `APPROVED_CHANGE`; it must never be hidden by a tolerance.

## Binance Account Trade authority

The USDⓈ-M Account Trade List (`GET /fapi/v1/userTrades`) is the first-party per-fill account record. The official response includes:

- `symbol`, `id`, `orderId`, `side`, `positionSide`, `buyer`, and `maker`;
- exact `price`, `qty`, and `quoteQty` strings;
- exact `commission` and `commissionAsset`;
- exact per-trade `realizedPnl`;
- trade `time`.

`fromId` is the trade-ID pagination boundary. Binance-maintained connector documentation also states that, without a time range, only recent seven-day data is returned; a requested time interval cannot exceed seven days; and `fromId` cannot be combined with `startTime`/`endTime`.

Consequences for G10H:

1. Account Trade identity is `(Account, Symbol, Trade ID)`; Order ID alone is not unique per fill.
2. Fill price/quantity, maker/taker, commission, commission asset, and realized PnL are direct comparison fields. G10H must not recompute the observed row from current commission rates.
3. Pagination defaults and time-window limits mean current API access cannot prove historical completeness. G12 must freeze all pages, query bounds, checksums, capture times, and gap evidence.
4. A static G10H fixture can validate normalization and first divergence, but cannot by itself claim a complete historical account archive.

Official source family:

- Account Trade List: <https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Account-Trade-List>
- Legacy searchable Account Trade List: <https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/trade/rest-api/Account-Trade-List>
- Binance-maintained connector implementation: <https://github.com/binance/binance-futures-connector-python/blob/main/binance/um_futures/account.py>

## Income-history authority

USDⓈ-M Income History (`GET /fapi/v1/income`) exposes account flows including `REALIZED_PNL`, `FUNDING_FEE`, `COMMISSION`, and `INSURANCE_CLEAR`. Binance-maintained connector documentation states:

- recent seven-day data is the default when no bounds are sent;
- omitting `incomeType` returns all flow types;
- `tranId` is unique within one income type for a user.

G10H uses Income History as an independent cash-flow cross-check:

- `FUNDING_FEE` may compare with G10E/G09D funding settlement;
- `COMMISSION` may reconcile Account Trade commissions at account-flow level;
- `REALIZED_PNL` may reconcile per-trade realized PnL aggregation;
- `INSURANCE_CLEAR` is unsupported economic evidence and must not be folded into ordinary realized PnL.

Income rows do not replace Account Trade rows for per-fill price, quantity, maker/taker, or trade identity. Duplicate economic representation across Account Trade and Income History must be linked, not double-booked.

Official source families:

- Income History: <https://developers.binance.com/docs/derivatives/usds-margined-futures/account/rest-api/Get-Income-History>
- Binance-maintained connector implementation: <https://github.com/binance/binance-futures-connector-python/blob/main/binance/um_futures/account.py>

## User-data event authority

### `ORDER_TRADE_UPDATE`

The USDⓈ-M order-update event separates:

- event generation time `E`;
- transaction/matching-engine time `T`;
- order trade time inside the order payload;
- Order ID and Trade ID;
- execution type and order status;
- last/cumulative filled quantity and last/average price;
- commission asset/amount;
- maker-side flag;
- reduce-only flag and position side;
- per-trade realized profit;
- special client-order identifiers beginning with `autoclose-` for liquidation and `adl_autoclose` for ADL.

These fields allow event-sequence parity and first-divergence attribution. They do not authorize reconstructing missing REST history from neighboring events. WebSocket receive/capture time remains distinct from `T` and `E`.

Official source:

- Order Update: <https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams/Event-Order-Update>
- User Data Stream ordering notes: <https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/user-data-streams>

### `ACCOUNT_UPDATE`

The account-update event is emitted when balances or positions change. An order status change that does not change account or position state does not produce this event. The event reason includes `ORDER`, `FUNDING_FEE`, and `INSURANCE_CLEAR` among other reasons.

The balance-change field `bc` excludes PnL and commission, so it is not the total cash delta for a fill. For cross-margin funding fees, Binance documents a reduced event containing the affected balance without position rows. G10H must therefore compare:

- wallet/cross-wallet balances as state observations;
- position amount, entry/break-even price, accumulated pre-fee realized PnL, and unrealized PnL as position observations;
- event reason and event ordering separately from per-fill commission and realized PnL.

Official source:

- Balance and Position Update: <https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams/Event-Balance-and-Position-Update>

## Liquidation and ADL authority

The USDⓈ-M User Force Orders endpoint distinguishes `LIQUIDATION` from `ADL` and returns Order ID, special client-order identity, status, price, average price, original/executed quantity, cumulative quote, side, position side, order type/TIF, and event/update times.

The public liquidation-order stream is only a market snapshot and may publish only the latest liquidation order within a one-second interval. It is not a complete user-account liquidation archive and cannot replace User Force Orders or account events.

G10H v1 comparison rules:

1. A G10G conservative bar-extreme liquidation audit may compare detection window/classification only.
2. Actual liquidation trigger time, order creation, average execution price, executed quantity, fees, bankruptcy/insurance effects, and ADL require archived user force-order/account evidence.
3. Conservative audit versus actual liquidation execution is not exact parity. It must be `NOT_COMPARABLE`, `MISMATCH`, or an explicit ADR-backed `APPROVED_CHANGE`.
4. `LIQUIDATION` and `ADL` must never be merged into one outcome.

Official sources:

- User Force Orders: <https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Users-Force-Orders>
- Liquidation Order Stream: <https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Liquidation-Order-Streams>
- Binance-maintained stream connector: <https://github.com/binance/binance-futures-connector-python/blob/main/binance/websocket/um_futures/websocket_client.py>

## Time and identity separation

G10H must preserve these distinct times:

- strategy decision time;
- legacy eligible/open execution time;
- Binance matching-engine transaction time `T`;
- Binance event generation time `E`;
- trade/order time;
- economic funding time;
- archive capture/availability time;
- local parity-normalization time, which is operational provenance and must not enter economic identity.

Rows with the same millisecond time remain distinct by source kind and stable provider IDs. Tuple order is never a conflict-resolution rule.

## Comparator contract

WP-00C already freezes Comparator Contract v1 and first-divergence report semantics:

- `exact` for canonical identity and exact values;
- `sequence` for ordered events and first differing item;
- `quantized` only with an explicit quantum and rounding policy;
- `explicit_tolerance` only on a named path with an explicit absolute and/or relative tolerance;
- `approved_change` only in intentional-semantic-change mode and only with a `docs/adr/...` reference;
- global epsilon is forbidden;
- comparator paths are unique, sorted, and non-overlapping;
- report verdict is `MATCH`, `MISMATCH`, or `APPROVED_CHANGE`, with the first divergence path/value/reason.

G10H adds a parity-case coverage classification before invoking the generic comparator:

- `COMPARABLE` — both sides possess the same semantic authority;
- `NOT_COMPARABLE_LEGACY_SCOPE` — `crypt-gemini` does not model the behavior;
- `NOT_COMPARABLE_PROVIDER_EVIDENCE` — required Binance account evidence is absent;
- `NOT_COMPARABLE_ARCHIVE_COMPLETENESS` — G12 completeness is not established.

`NOT_COMPARABLE` cannot be represented as numeric tolerance or silently omitted from the report.

## Frozen parity layers

First divergence is evaluated in this order:

1. source/snapshot and case identity;
2. decision/action sequence;
3. order intent and rule/admission result;
4. order-event lifecycle;
5. fill identity, price, quantity, liquidity/maker status;
6. fee amount/currency and fee-rule identity;
7. position transition and realized PnL;
8. funding slot/rate/mark/cash flow;
9. Journal and generic Ledger effects;
10. margin projection and portfolio snapshot;
11. liquidation-audit classification;
12. actual liquidation/ADL execution, when authoritative evidence exists;
13. final result and run-end identity.

An earlier mismatch cannot be hidden by a later aggregate match. Final PnL equality does not establish fill, fee, funding, position, margin, or liquidation parity.

## Intentional differences requiring ADRs

At minimum, G10H must explicitly classify these known differences:

- `crypt-gemini` long-only executor versus G10G open/reduce/flip journey;
- legacy next-open full-fill convention versus Binance matching-engine/order-book execution;
- fixed legacy fee rate versus per-fill Binance maker/taker commission;
- fixed legacy slippage versus actual fill prices;
- exposure-normalized legacy accounting versus contract/quantity/price-scale accounting;
- legacy funding shortcut versus G10E/G09C/G09D slot/mark/settlement accounting;
- legacy reserved-margin shortcut versus G10C/G09E/G09F account margin projection;
- conservative bar-extreme liquidation audit versus Binance liquidation/ADL execution;
- legacy operational IDs/timestamps versus canonical semantic identity.

Each approved difference needs a stable `docs/adr/...` reference. An ADR documents the difference; it does not grant decision-grade or deployment authorization.

## Development and qualification boundary

G10H outputs remain development evidence unless all required provider records and G12 completeness evidence are supplied. Passing G10H does not change the frozen G10G profile keys or authorize live trading.

G10H does not own:

- network clients, secrets, or authenticated requests;
- raw provider acquisition/parsing/storage;
- historical pagination and retention proof;
- order-book reconstruction or a Binance matching-engine model;
- liquidation, bankruptcy, insurance-fund, or ADL simulation;
- multi-assets, isolated margin, Hedge Mode, BNB discounts, negative rebates, or Portfolio Margin;
- deployment authorization.

Those boundaries remain with G12, a future matching-engine/liquidation model, and explicit deployment qualification gates.

## Research access note

Direct fetches of `developers.binance.com` were blocked in this environment because the local resolver returned a fake-IP address in `198.18.0.0/15`. Claims above were preserved through official Binance pages indexed by search and Binance-maintained GitHub connector sources. No third-party behavioral source is treated as authoritative.
