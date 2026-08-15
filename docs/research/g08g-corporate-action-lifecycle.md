# G08G Corporate Action Adjustment and Payment Readiness

## Decision status

G08G remains **DRAFT / BLOCKED**, but the blockers are now decomposed into executable repository-owned foundation work. No missing provider fact is required to begin the first milestone.

This note does not authorize Corporate Action translation before the replayable Lot foundation passes, and it does not qualify a real market/profile.

## Verified current state

- `AccountingJournalEntry` owns balance and attribution effects but no Lot effects.
- `GenericLedger` projects Position quantity and explicitly rejects populated `PositionBalance.lots`.
- `CashInstrumentAccounting` returns immutable `open_lots`, while Backtest Runtime stores them in mutable `lot_books` side-state.
- `PositionLot.unit_cost` is fixed-scale and is not an authoritative total cost basis.
- G08F returns immutable gross cash, bonus-share, and capitalization-share entitlement bound to its announcement/register/calendar/rule evidence. It performs no Journal, Ledger, Lot, Settlement, availability, or tax mutation.
- Generic `SettlementObligation` is Fill-bound through `source_fill_id`; G08G must not misuse it for a Corporate Action.

## Frozen foundation direction

### One Journal Lot-effect contract

Add one Domain value, provisionally named `PositionLotChange`, with exact before/after state:

- create: `before=None`, `after=PositionLot`;
- replace: exact current `before`, exact replacement `after` with the same Lot/Position identity;
- close: exact current `before`, `after=None`.

`AccountingJournalEntry` gains an ordered canonical tuple of these changes. Empty legacy entries omit the new field and preserve existing v1 canonical bytes. Entries carrying Lot changes publish additive schema-v2 canonical evidence.

`GenericLedger` applies changes strictly against the replayed current Lot state, rejects missing/mismatched before-state, duplicate Lot effects, key/account/Venue/scale mismatch, and quantity/Lot-total divergence, then projects canonical populated `PositionBalance.lots`.

This is the only authoritative create/replace/close path for both Fill accounting and G08G. No Lot registry, generic effect framework, mutable Lot store, or second Ledger is permitted.

### Authoritative exact total cost basis

Extend the existing `PositionLot` with optional `total_cost_basis: Money` rather than introduce a rational or parallel Lot type.

`Money` is sufficient because Fill notional is already quantized to an exact currency scale. Corporate Action share adjustment preserves that exact total unchanged; its displayed `unit_cost` may be explicitly re-quantized without becoming authoritative.

For a partial consumption, the existing explicit accounting quantization/rounding policy allocates consumed total basis and the remainder receives the exact difference, so consumed plus remaining `Money` always equals the prior total. `LotConsumption` carries the consumed authoritative total basis.

Legacy Lots with no total basis retain their canonical v1 bytes. New exact-basis Lots and consumptions publish additive v2 canonical bodies. Mixed or identity-inconsistent exact-basis state fails closed.

### Runtime authority migration

The same `CashInstrumentAccounting` implementation must emit Journal Lot changes and exact basis; there is no `book_fill_v2` economic engine. Legacy object construction remains readable, but new accounting output becomes replay-authoritative.

After Ledger replay parity is proven, Runtime removes `PositionLotBook`, `PositionLotState`, `lot_books`, and result-side replacement of Lot state. Dispatchers read current Lots only from `LedgerState.position_balances`, append the returned Journal entry once, and obtain the next Lot state by normal Ledger replay.

## Narrow G08G v1 scope

After the foundation passes, G08G v1 may support only facts already expressible without inference:

- standard domestic CNY cash-auction XSHG/XSHE entitlements already validated by G08F;
- exactly one eligible positive acquisition Lot for any share delivery; multiple or zero eligible Lots fail closed;
- cash payment only at the declared Payment trigger, with delivered gross cash exact-equal to G08F entitlement;
- XSHE bonus/capitalization delivery only at the declared Listing trigger, with delivered whole-share quantities exact-equal to G08F entitlement;
- explicit immediate availability evidence: paid cash is tradable, withdrawable, and margin-eligible at Payment; delivered shares are sellable at Listing;
- explicit tax disposition enum with `NOT_APPLICABLE`, `APPLIED`, and `DEFERRED_UNSUPPORTED`, while v1 success accepts only `NOT_APPLICABLE` with zero withholding and net cash equal to gross cash.

Cash and share legs produce separate immutable Journal entries when their declared triggers differ. No entry is produced early. A share entry increases Position quantity, replaces the one eligible Lot, preserves exact total cost basis, and derives non-authoritative unit cost under a caller-supplied quantization policy.

The settlement evidence must bind entitlement hash, action Event identities, exact delivered value, declared trigger instant, immutable source-evidence hash, availability facts, and tax disposition. Suspended, delayed, revised, cancelled, mismatched, fractional, sub-cent, withheld, deferred-tax, multi-Lot, or unavailable cases fail closed in v1.

## Failure precedence to freeze with implementation

1. invalid type/context/identity;
2. entitlement/evidence hash mismatch;
3. unsupported venue/action/tax/availability scope;
4. trigger mismatch or early invocation;
5. delivered value mismatch or fractional evidence;
6. eligible-Lot cardinality/state mismatch;
7. exact-basis/quantization mismatch;
8. duplicate/conflicting Journal or Lot effect.

No partial result or partial Journal tuple is returned.

## Milestone order

1. **F1 — Domain/Ledger Lot replay:** additive Lot-change and exact-basis contracts; full/prefix/resume/conflict tests; legacy v1 byte parity.
2. **F2 — Fill/Runtime authority migration:** Fill and Fee changes emit the same effects; Runtime mutable Lot authority is removed; economic parity and runtime replay tests pass.
3. **F3 — Corporate Action translation:** typed lifecycle/delivery/tax evidence and pure cash/share translators with static golden fixtures.
4. **G08G acceptance:** focused/full validation and independent review; only then mark PASSED.

## Non-goals

No provider lookup, entitlement recomputation, multi-Lot allocation, cash-in-lieu, withholding calculation, deferred-tax tracking, delayed/suspended payment handling, Corporate Action-specific Settlement fork, raw-price rewrite, Runtime orchestration branch, or G08H market qualification.
