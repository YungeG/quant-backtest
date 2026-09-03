# ADR 0012: Tushare Dividend and Simulated Register Development Convention

- Status: Accepted
- Date: 2026-09-03
- Scope: Ticket #27 / `000703.SZ` development route

## Decision

For the finite `000703.SZ` development window
`[2024-01-02T00:00:00+08:00, 2026-09-01T00:00:00+08:00)`, one retained
Tushare `dividend(ts_code=000703.SZ)` response is the sole corporate-action
source. Its returned implementation rows are treated as correct action facts;
a retained zero-row response is treated as no action for that captured scope.

At a qualifying record boundary, the simulated ledger's position after the
existing 15:00 Asia/Shanghai record-close boundary is the registered position.
It is not a ChinaClear, broker, or account-statement snapshot.

The implementation must be additive: a V2 profile/action contract may carry a
canonical ordered action set and a simulated-register policy, while V1 profile
bytes and public behavior remain unchanged. It may not precompute a future
simulated position during profile composition. Runtime derives each registered
quantity only from its then-current simulated ledger state.

## Consequences

- Multiple returned actions may be represented; the singular V1 declaration
  contract is not reused as a hidden aggregate.
- A malformed, duplicate, out-of-window, non-implementation, or unsupported
  action row fails closed.
- All resulting artifacts remain development-only; decision-grade, live,
  deployment, broker-parity, ChinaClear-parity, tax-parity, and legal claims
  remain false.
- This ADR supersedes Ticket #27's prior source-closure blocker only for the
  stated development convention. It does not make Tushare a general corporate
  action authority.
