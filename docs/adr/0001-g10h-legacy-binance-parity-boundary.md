# ADR 0001: G10H Legacy/Binance Parity Boundary

- Status: Accepted
- Date: 2026-08-11
- Gate: G10H

## Context

The frozen `crypt-gemini` snapshot models a long-only, next-open, deterministic-cost research executor. G10G models a development-only Binance USDⓈ-M linear-perpetual journey through generic Runtime seams. Binance account evidence can additionally supply actual fills, commissions, realized PnL, funding flows, account updates, and force orders.

These authorities overlap, but they are not interchangeable. Treating final PnL equality as full parity would hide earlier differences in decisions, order lifecycle, fills, fees, funding, position accounting, margin, and liquidation.

## Decision

G10H reports first divergence by ordered semantic layer.

- Exact comparison is used only where both sides possess the same authority.
- Quantization or tolerance is path-local and explicit; global epsilon is forbidden.
- Missing legacy scope, missing provider evidence, and unproved archive completeness are reported as `NOT_COMPARABLE`, never as equality.
- Known legacy/G10G semantic differences may use Comparator Contract v1 `approved_change` rules referencing this ADR.
- Binance Account Trade, Income History, user-data events, and User Force Orders remain distinct evidence families and are linked without double-booking.
- A passing G10H gate means the parity report is complete and truthful. It does not require a `MATCH` verdict and does not authorize decision-grade or deployment use.

## Approved legacy/G10G differences

The following are intentional for G10H v1:

1. long-only legacy execution versus G10G open/reduce/flip position transitions;
2. next-open deterministic full fills versus Binance matching-engine/order-book execution;
3. fixed legacy fee/slippage rates versus per-fill maker/taker commission and observed fill prices;
4. exposure-normalized legacy accounting versus exact contract quantity/price scales;
5. legacy funding shortcut versus slot/publication/mark/settlement accounting;
6. legacy reserved-margin shortcut versus tiered instrument/account margin projection;
7. conservative bar-extreme liquidation audit versus actual liquidation or ADL execution;
8. legacy operational identifiers versus canonical semantic identity.

Each comparison document must still expose the affected layer and first differing item. This ADR cannot approve omitted evidence or a global aggregate tolerance.

## Consequences

- G10H can finish with `MATCH`, `MISMATCH`, `APPROVED_CHANGE`, or explicit `NOT_COMPARABLE` layer coverage.
- Provider-history completeness remains blocked on G12.
- Matching-engine and liquidation execution remain unsupported models unless separately implemented and frozen.
- G10G remains development-only and `deployment_authorized=false`.
