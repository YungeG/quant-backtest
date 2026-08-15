# G08G Corporate Action Adjustment and Payment Readiness

## Decision status

G08G is **PASSED**. F1 Journal/Ledger Lot replay, F2 Fill/Runtime authority migration, and F3 Corporate Action cash/share translation passed. The readiness contract is frozen at `8cf6a65e8fe1bb36c96cd6302534f101b26b3899`, RED fixtures at `bc1e902bf04109eaa8a329fd8d44a3c758fa8317`, and implementation at `547e16f2d7a9331f9207abfca7ea7c0593fc84fc`.

This contract does not qualify a real market or authorize deployment. G08H retains provider/payment/revision scope, complete real-market composition qualification, MarketBundle mapping, Runtime wiring, and parity.

## Ownership and dependencies

F3 is owned by `trading-kernel profiles/cn_a_share` and adds one module:

`packages/trading-kernel/src/crypto_quant_trading/profiles/cn_a_share/corporate_action_accounting.py`

It consumes:

- G08F `CnAShareCorporateActionEntitlement` and `CnAShareCorporateActionSourceRef`;
- existing Domain `AccountingJournalEntry`, `BalanceChange`, `PositionLot`, `PositionLotChange`, `Money`, identifiers, and numeric values;
- existing `QuantizationPolicy`;
- existing `AccountingJournal` and `GenericLedger` append/replay authority.

It adds no stateless class, Protocol, registry, generic effect framework, `ProfilePortType`, `ProfilePortOutcome`, provider adapter, Runtime dispatcher, Settlement fork, or new Lot authority. It performs no network, filesystem, process, database, dynamic-import, or wall-clock access.

## Frozen public API

Export only from `crypto_quant_trading.profiles.cn_a_share`, not top-level `crypto_quant_trading`:

```python
CnAShareCorporateActionTaxDisposition
CnAShareCorporateActionDeliveryStatus
CnAShareCashPaymentEvidence
CnAShareShareDeliveryEvidence
CnAShareCashPaymentRequest
CnAShareShareDeliveryRequest
CnAShareCorporateActionTranslationFailureCode
CnAShareCorporateActionTranslationFailure
CnAShareCashPaymentOutcome
CnAShareShareDeliveryOutcome
translate_corporate_action_cash_payment
translate_corporate_action_share_delivery
```

`CnAShareCorporateActionTaxDisposition` values are `not_applicable`, `applied`, and `deferred_unsupported`. `CnAShareCorporateActionDeliveryStatus` values are `confirmed`, `suspended`, and `cancelled`. V1 success accepts only `confirmed` and `not_applicable`.

There is no separate success-result wrapper: the existing `AccountingJournalEntry` is the success value. The two concrete outcomes contain their request and exactly one of `journal_entry` or the shared failure.

## Typed evidence and requests

Both immutable, slotted evidence types bind:

- canonical `evidence_id`;
- `source_ref: CnAShareCorporateActionSourceRef`;
- G08F `entitlement_hash`;
- `corporate_action_id`;
- announcement `event_id` and `event_hash`;
- delivery `status`;
- exact `trigger_at: SimulationInstant`;
- evidence `available_at: SimulationInstant`.

The frozen deterministic ordering boundaries are Asia/Shanghai 09:30 on the applicable declared date: Payment uses `TimelinePhase(110, "corporate_action_payment")` and `SourceSequence(0)`; Listing uses `TimelinePhase(120, "corporate_action_listing")` and `SourceSequence(0)`. These are system conventions rather than claims about external clearing completion. V1 accepts only `available_at == trigger_at`; it does not backdate later evidence or treat advance notice as delivered evidence.

Cash evidence additionally binds `gross_cash`, `withholding`, `net_cash`, `tax_disposition`, `tradable`, `withdrawable`, and `margin_eligible`.

Share evidence additionally binds separate `delivered_bonus_quantity` and `delivered_capitalization_quantity`, `withholding: Money`, `tax_disposition`, and `sellable`.

Requests are exactly:

```python
CnAShareCashPaymentRequest(
    entitlement,
    evidence,
    cash_key,
    journal_entry_id,
    recorded_at,
)

CnAShareShareDeliveryRequest(
    entitlement,
    evidence,
    open_lots,
    unit_cost_quantization,
    journal_entry_id,
    recorded_at,
)
```

Constructors reject malformed types, invalid existing Domain values, and noncanonical text only. Semantic scope, identity, status, tax, availability, timing, value, Lot, basis, and quantization defects remain structured translator outcomes.

G08G does not infer provider facts or trigger times. Evidence supplies the exact trigger. Cash must identify the entitlement's declared Payment TradingDate/system phase; shares must identify the declared Listing TradingDate/system phase. G08H owns provider mapping and completeness.

## Success contract

### Cash payment

Success requires a positive payable cash leg, exact entitlement/evidence/account/Instrument/Event identity, confirmed status, `NOT_APPLICABLE`, CNY Scale-2 zero withholding, `net_cash == gross_cash`, all three immediate-availability flags true, the exact frozen Payment trigger, `available_at == trigger_at`, and `recorded_at >= trigger_at` under full `SimulationInstant` order.

Return one existing Journal entry:

- `AccountingEntryType.CORPORATE_ACTION_CASH_PAID`;
- effective time `evidence.trigger_at.instant`;
- one positive cash `BalanceChange` for `net_cash`;
- no Lot changes, realized PnL, fees, financing, Settlement, or availability mutation.

### Share delivery

Success requires a positive XSHE bonus/capitalization leg, confirmed status, `NOT_APPLICABLE`, CNY Scale-2 zero withholding, `sellable=True`, the exact frozen Listing trigger, `available_at == trigger_at`, `recorded_at >= trigger_at` under full `SimulationInstant` order, separate delivered values exact-equal to G08F entitlement, whole Scale-0 shares, and exactly one eligible current Lot.

The eligible Lot exact-matches account/Venue/Instrument position identity, has positive current quantity and non-null positive unit cost, and carries strictly positive authoritative CNY Scale-2 `total_cost_basis`. Its current quantity is not required to equal G08F registered quantity because post-Record sales do not alter captured entitlement.

Return one existing Journal entry:

- `AccountingEntryType.CORPORATE_ACTION_POSITION_ADJUSTED`;
- effective time `evidence.trigger_at.instant`;
- one position `BalanceChange` for bonus plus capitalization shares;
- exactly one `PositionLotChange(before=old_lot, after=adjusted_lot)`;
- no realized PnL, fees, financing, Settlement, or availability mutation.

The replacement preserves Lot ID, source ID, position key, opened time, allocated fees, and exact total cost basis. It increases current quantity by delivered shares and derives only non-authoritative unit cost using the supplied existing `QuantizationPolicy`. V1 requires the policy target scale to equal the prior unit-cost scale and the result to remain positive. The translator does not return `open_lots`; Journal append and Generic Ledger replay remain authoritative.

## Exact failure precedence

1. `CONTEXT_MISMATCH`
2. `ENTITLEMENT_EVIDENCE_MISMATCH`
3. `UNSUPPORTED_ACTION_SCOPE`
4. `UNSUPPORTED_DELIVERY_STATUS`
5. `UNSUPPORTED_TAX_DISPOSITION`
6. `NONZERO_WITHHOLDING`
7. `UNSUPPORTED_AVAILABILITY`
8. `TRIGGER_MISMATCH`
9. `EVIDENCE_NOT_AVAILABLE`
10. `UNSUPPORTED_FRACTIONAL_SHARE`
11. `DELIVERED_VALUE_MISMATCH`
12. `EARLY_INVOCATION`
13. `ELIGIBLE_LOT_CARDINALITY_MISMATCH`
14. `LOT_STATE_MISMATCH`
15. `EXACT_COST_BASIS_MISMATCH`
16. `UNIT_COST_QUANTIZATION_MISMATCH`

`UNSUPPORTED_ACTION_SCOPE` covers absent/zero payable legs, XSHG share delivery, and non-XSHE share actions. `EVIDENCE_NOT_AVAILABLE` exact-covers `available_at != trigger_at`. `DELIVERED_VALUE_MISMATCH` covers cash gross/net versus G08F entitlement after the earlier withholding guard and share bonus/capitalization mismatch after the earlier fractional guard, keeping intrinsic evidence attribution stable across retries. `ELIGIBLE_LOT_CARDINALITY_MISMATCH` checks absolute `len(open_lots) != 1` without filtering; a single Lot with wrong identity/state reaches `LOT_STATE_MISMATCH`. Every semantic failure returns only the first applicable failure and no partial Journal or Lot output.

Duplicate Journal IDs, conflicting replay, and stale/mismatched Lot before-state are not translation failures. Existing `AccountingJournal` and `GenericLedger` reject them during append/replay.

## Canonical identities

Every new value uses `schema_version=1`, an explicit type literal, canonical tuple order, and the applicable `evidence_hash`, `request_hash`, `failure_hash`, or `outcome_hash`.

Type literals:

- `cn_a_share_cash_payment_evidence`;
- `cn_a_share_share_delivery_evidence`;
- `cn_a_share_cash_payment_request`;
- `cn_a_share_share_delivery_request`;
- `cn_a_share_corporate_action_translation_failure`;
- `cn_a_share_cash_payment_outcome`;
- `cn_a_share_share_delivery_outcome`.

Failure subject IDs are ordered exactly as `(code, leg, corporate_action_id, entitlement_hash, evidence_id, evidence_hash, account_id, instrument_id, journal_entry_id)`, with leg `cash_payment` or `share_delivery`.

Journal `source_ids` order is corporate-action ID, entitlement hash, announcement event ID, announcement event hash, evidence ID, evidence hash.

## Static fixtures, artifacts, and qualification flags

Fixtures:

- `tests/fixtures/kernel/profiles/cn_a_share/corporate-action-accounting-v1.json`
  - ID `cn-a-share-corporate-action-accounting-v1`
- `tests/fixtures/kernel/integration/corporate-action-journal-replay-v1.json`
  - ID `cn-a-share-corporate-action-journal-replay-v1`

Freeze CA-XSHE-001 CNY 70 payment and 210-share delivery against one current 500-share exact-basis Lot, proving current quantity need not equal the frozen 700-share Record entitlement; CA-XSHG-001 CNY 200 payment; Journal IDs with repeated 6/7/8 payloads; every failure code; multi-defect precedence; strict XOR rejection; full/prefix/resume replay; duplicate/conflict/stale-before-state rejection through existing authorities; unchanged G08F entitlement hash; and unchanged raw prices.

Expected generated evidence artifacts are `build/acceptance/g08g-f3-pytest.xml`, `build/acceptance/g08g-f3-mypy.txt`, and `build/acceptance/g08g-f3-import-boundary-report.json`.

All fixtures/evidence state `grade=development`, `decision_grade_eligible=false`, `profile_qualified=false`, and `deployment_authorized=false`. Golden hashes are generated and frozen in the RED fixture commit, not invented in implementation.

## Exact RED commands

```bash
uv run pytest -q \
  tests/kernel/profiles/cn_a_share/test_corporate_action_accounting.py \
  tests/kernel/profiles/cn_a_share/test_corporate_action_accounting_golden.py \
  tests/kernel/integration/test_corporate_action_journal_replay.py
```

```bash
uv run pytest -q \
  tests/domain/accounting \
  tests/kernel/accounting \
  tests/kernel/journal \
  tests/kernel/ledger \
  tests/runtime/engine/test_g08g_runtime_lot_authority.py
```

```bash
uv run pytest -q \
  tests/architecture/test_g08g_corporate_action_accounting_boundary.py \
  tests/architecture/test_public_api_imports.py \
  tests/architecture/test_network_isolation.py \
  tests/architecture/test_repository_cleanliness.py

uv run python tools/architecture/check_import_boundaries.py \
  --root . \
  --policy architecture/import-boundaries.toml \
  --report build/acceptance/g08g-f3-import-boundary-report.json
```

## Residual risks retained by G08H

Provider event/payment mapping, payment and register revision closure, delayed/suspended/cancelled lifecycle composition, real-security/account/distribution-scope qualification, taxable-transfer behavior, real-market profile qualification, MarketBundle mapping, Runtime wiring, decision-grade eligibility, and deployment authorization remain outside G08G.
