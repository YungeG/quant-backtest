# 000703 corporate-action development V2

## Scope

Implement ADR 0012 for the finite `000703.SZ` development window only. Preserve
all V1 profile and corporate-action contracts. No live, decision-grade, broker,
ChinaClear, tax-parity, or legal claim is added.

## Dependency graph

1. **Dividend evidence** — retain and verify one proxy-delivered
   `dividend(ts_code=000703.SZ)` response. Produce canonical action rows and a
   source snapshot. Malformed, duplicate, nonterminal, or unsupported rows fail
   closed.
2. **Action-set contract** — map retained implementation rows to an ordered,
   immutable multi-action set. It consumes the dividend source snapshot and
   produces no account quantity.
3. **Profile V2 contract** — add an action-set/simulated-register policy beside
   the frozen V1 composition request. It consumes the action set and declares
   only the record-close derivation rule; it does not invent future holdings.
4. **Runtime register projection** — at each action's record-close boundary,
   derive a `CnAShareRegisteredPositionSnapshot` from the current simulated
   ledger. It consumes the V2 profile action set and ledger state.
5. **Entitlement and delivery fan-in** — feed the derived snapshot and mapped
   action to existing entitlement/payment logic, once per action in canonical
   record-date/action-ID order. Validate dynamic cash/share results and preserve
   existing T+1 behavior.

Nodes 1 and 2 are evidence/contract work. Nodes 3–5 share Profile/Runtime
seams and must have one writer in order.

## Acceptance gates

- The dividend raw bytes, receipt, source snapshot, row mapping, and action-set
  identity are reproducible.
- The V2 action set is ordered, finite, and exact-covers the retained source
  scope; V1 APIs and fixture bytes stay unchanged.
- Record-date quantity changes when the simulated ledger changes; it is never
  copied from a broker/ChinaClear claim.
- Multiple actions process in deterministic order; malformed action rows,
  missing record state, and duplicate delivery fail closed.
- All outputs retain false decision-grade, live, and deployment flags.
