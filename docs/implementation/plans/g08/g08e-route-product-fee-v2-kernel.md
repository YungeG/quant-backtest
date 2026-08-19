---
id: G08E-ROUTE-PRODUCT-FEE-V2A
proposed_readiness: READY_FOR_CONTRACT_RED
registry_status: PENDING_PARENT_ACCEPTANCE_MATRIX_FAN_IN
owner: trading-kernel profiles/cn_a_share
produces:
  - pure route/product-aware A-share fee Kernel contract
  - XSHE-only finite v1-to-v2 compatibility projection
consumes:
  - immutable G08E v1 fee/tax contract and fixture
  - ADR 0005
depends_on:
  contract: [G08E]
  evidence: [ADR-0005]
  write_conflict: [kernel-cn-a-share-fee-tax]
fan_out: [G08E-ROUTE-PRODUCT-FEE-V2B, G08E-ROUTE-PRODUCT-FEE-V2C]
---

# G08E-V2A Pure Kernel route/product fee contract

## Scope and exclusion

Proposed `READY_FOR_CONTRACT_RED`, pending parent Acceptance Matrix fan-in. The parent [Acceptance Matrix](../../acceptance-matrix.md) is the sole current status authority; this frontmatter is not a second Gate status. This is a pure Kernel contract. It does not import Runtime, resolved profiles, profile registries, profile/build manifests, `ExecutionCaseSemanticSpec`, Financial Dispatch, Runner, or Semantic Run. Runtime selection and semantic binding are exclusively deferred to [V2B](g08e-route-product-fee-v2-runtime-binding.md).

The initial finite compatibility scope is exactly `DOMESTIC + ORDINARY_A_SHARE + XSHE + EQUITY + CNY + AUCTION + trade_notional`. `NORTHBOUND_STOCK_CONNECT`, `PREFERRED_STOCK`, and `ETF` are named enums only; they require separately evidenced v2 books. Non-notional portfolio, instruction, settlement, safekeeping, collateral, and corporate-action service costs are out of scope.

## Frozen v1 boundary

Do not modify `commission_tax.py`, generic fee/tax ports, generic fee arithmetic, Runtime, Builder, registry, root exports, fixtures, or publication artifacts. V1 public signatures, canonical bodies/hashes, `cn_a_share.__all__` members/order, and these raw bytes remain exact:

```text
3ef26743bc9cebfe546f77812c6773cbdf3353e0337d03ed512d5f1c396f702b  tests/fixtures/kernel/profiles/cn_a_share/commission-tax-v1.json
aa032668a5207b61b6c8815894e0087f1c1e734d41e9707c7d32111b6c1cd79f  tests/fixtures/runtime/profiles/cn-a-share-resolved-profile-composition-v1.json
08358c1c0d2144fb23c1b1c8862fa6c879bd285533e5fa415e5cc0273013e905  tests/fixtures/runtime/engine/cn-a-share-resolved-profile-development-journey-v1.json
19017a07fbfd2da954483648fb168d87212f88e92fccca7c28fb0a514b202515  tests/fixtures/market_data/rule_authorities/cn-a-share-development-v1/declaration.json
7a95188cf05d401fcaed80b548f82f22f0b9bc23f6423c6ff1190de775291f7d  tests/fixtures/market_data/rule_authorities/cn-a-share-development-v1/publication.expected.json
```

## Production surface

Add only:

```text
packages/trading-kernel/src/crypto_quant_trading/profiles/cn_a_share/commission_tax_v2.py
```

Append the declared v2 names to `crypto_quant_trading.profiles.cn_a_share.__all__` after every frozen v1 member; do not export them from `crypto_quant_trading` root. The module imports stdlib, `crypto_quant_domain`, existing generic fee/reservation/port contracts, the shared immutable `CnAShareFeeTradeMechanism` from v1 `commission_tax`, and v1 `CnAShareMarketFeeBand`, `CnAShareMarketFeeRuleBook`, `CnAShareStampDutyBand`, `CnAShareStampDutyRuleBook`, and `CnAShareFeeRuleSourceRef` only for projection. It performs no I/O and imports no Runtime, Builder, provider, filesystem, network, database, process, wall clock, dynamic loader, or test support.

All v2 dataclasses are frozen/slotted. Every v2 canonical body has `schema_version: 1`, fixed `_v2` type literal, declared field order, and a derived hash excluded from its preimage. Constructors enforce exact primitive/concrete/canonical structure only; semantic operations return the first structured failure. No field or parameter has a default.

Append exactly these names after the frozen v1 `__all__` sequence: `CnAShareExecutionAccessRoute`, `CnAShareFeeProductClass`, `CnAShareFeeAssessmentPurposeV2`, `CnAShareFeeExecutionScopeV2`, `CnAShareFeeExecutionSelectionV2`, `CnAShareFeeExecutionAuthorityV2`, `CnAShareFeeExecutionAuthorityFailureCodeV2`, `CnAShareFeeExecutionAuthorityFailureV2`, `CnAShareFeeExecutionBindingV2`, `CnAShareFeeExecutionBindingFailureCodeV2`, `CnAShareFeeExecutionBindingFailureV2`, `CnAShareCashFeeRuleQueryV2`, `CnAShareFeeQueryConstructionFailureCodeV2`, `CnAShareFeeQueryConstructionFailureV2`, `CnAShareMarketFeeBandV2`, `CnAShareMarketFeeRuleBookV2`, `CnAShareStampDutyBandV2`, `CnAShareStampDutyRuleBookV2`, `CnAShareMarketFeeRuleResolutionV2`, `CnAShareStampDutyRuleResolutionV2`, `CnAShareFeeRuleFailureCodeV2`, `CnAShareFeeRuleFailureV2`, `CnAShareCashMarketFeePolicyV2`, `CnAShareCashStampDutyTaxPolicyV2`, `CnAShareFeeReservationBufferV2`, `CnAShareDomesticOrdinaryFeeProjectionV2`, `CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2`, `CnAShareDomesticOrdinaryFeeProjectionFailureV2`, `create_cn_a_share_fee_execution_authority_v2`, `bind_cn_a_share_fee_execution_v2`, and `project_cn_a_share_domestic_ordinary_fee_rules_v2`.

### Enums and pure scope

```python
class CnAShareExecutionAccessRoute(str, Enum):
    DOMESTIC = "domestic"
    NORTHBOUND_STOCK_CONNECT = "northbound_stock_connect"

class CnAShareFeeProductClass(str, Enum):
    ORDINARY_A_SHARE = "ordinary_a_share"
    PREFERRED_STOCK = "preferred_stock"
    ETF = "etf"

class CnAShareFeeAssessmentPurposeV2(str, Enum):
    RESERVATION = "reservation"
    FINAL_FILL = "final_fill"
```

`CnAShareFeeExecutionScopeV2` fields, in order:

```text
account_id: str
venue_id: VenueId
instrument: InstrumentDefinition
instrument_id: InstrumentId
instrument_type: InstrumentType
quote_currency_id: CurrencyId
settlement_currency_id: CurrencyId
trade_mechanism: CnAShareFeeTradeMechanism
coverage_from: UtcInstant
coverage_to_exclusive: UtcInstant
allowed_order_sides: tuple[OrderSide, ...]
access_route: CnAShareExecutionAccessRoute
fee_product_class: CnAShareFeeProductClass
```

Canonical type is `cn_a_share_fee_execution_scope_v2`; `scope_hash = canonical_sha256(body)`. Structure requires exact nested identities, canonical unique side tuple, and no inferred route/product. Constructor invariants are exact and run before Authority build: `venue_id == VenueId("xshe")` else `ValueError("scope venue_id must be XSHE")`; `instrument_type is InstrumentType.EQUITY` else `ValueError("scope instrument_type must be EQUITY")`; `quote_currency_id == CurrencyId("CNY")` else `ValueError("scope quote_currency_id must be CNY")`; `settlement_currency_id == CurrencyId("CNY")` else `ValueError("scope settlement_currency_id must be CNY")`; `trade_mechanism is CnAShareFeeTradeMechanism.AUCTION` else `ValueError("scope trade_mechanism must be AUCTION")`; and finite `coverage_from < coverage_to_exclusive` else `ValueError("scope coverage interval must be finite and non-empty")`. Caller selection of this value is owned by V2B.

`CnAShareFeeExecutionSelectionV2` fields/order are `selection_key: str`, `selection_version: int`, `access_route`, `fee_product_class`, `market_fee_rule_book: CnAShareMarketFeeRuleBookV2`, `market_fee_rule_book_hash: str`, `stamp_duty_rule_book: CnAShareStampDutyRuleBookV2`, `stamp_duty_rule_book_hash: str`, `market_fee_component_ref: ProfileComponentRef`, `stamp_duty_component_ref: ProfileComponentRef`. Its type is `cn_a_share_fee_execution_selection_v2`; `selection_hash` is derived.

The exact pure authority API is `create_cn_a_share_fee_execution_authority_v2(scope: CnAShareFeeExecutionScopeV2, selection: CnAShareFeeExecutionSelectionV2, /) -> CnAShareFeeExecutionAuthorityV2 | CnAShareFeeExecutionAuthorityFailureV2`. It sets `authority_key` exactly to `equity.cn_a_share.cash.fee-execution-authority.route-product.v2`, sets `authority_version` exactly to `2`, then evaluates `SCOPE_SELECTION_MISMATCH`, `RULE_BOOK_SCOPE_MISMATCH`, and `COMPONENT_REF_MISMATCH` in declaration order. `CnAShareFeeExecutionAuthorityV2` is pure Kernel selection, not profile provenance. Fields/order are `authority_key: str`, `authority_version: int`, `scope`, `scope_hash`, `selection`, `selection_hash`, `access_route`, `fee_product_class`, `market_fee_rule_book`, `market_fee_rule_book_hash`, `stamp_duty_rule_book`, `stamp_duty_rule_book_hash`, `market_fee_component_ref`, `stamp_duty_component_ref`. Type is `cn_a_share_fee_execution_authority_v2`; `authority_version == 2`; `authority_hash` is derived. The pure authority constructor validates Scope/Selection equality, exact book/hash/ref equality, route/product equality, and no interchangeable market/stamp book pair.

`CnAShareFeeExecutionAuthorityFailureCodeV2` order is `SCOPE_SELECTION_MISMATCH`, `RULE_BOOK_SCOPE_MISMATCH`, `COMPONENT_REF_MISMATCH`. `CnAShareFeeExecutionAuthorityFailureV2` fields/order are `scope`, `scope_hash`, `selection`, `selection_hash`, `code`, `subject_ids`; type is `cn_a_share_fee_execution_authority_failure_v2`. Prefix is `(code.value, scope_hash, selection_hash)`. Exact suffixes are respectively `( "scope_access_route", scope.access_route.value, "selection_access_route", selection.access_route.value, "scope_fee_product_class", scope.fee_product_class.value, "selection_fee_product_class", selection.fee_product_class.value )`; `( "market_fee_rule_book_hash", selection.market_fee_rule_book_hash, "stamp_duty_rule_book_hash", selection.stamp_duty_rule_book_hash, "scope_venue_id", scope.venue_id.value )`; and `( "market_fee_component_digest", selection.market_fee_component_ref.component_digest, "stamp_duty_component_digest", selection.stamp_duty_component_ref.component_digest )`. No subject tuple is deduplicated or sorted.

| code | exact authority-failure suffix |
| --- | --- |
| `SCOPE_SELECTION_MISMATCH` | `( "scope_access_route", scope.access_route.value, "selection_access_route", selection.access_route.value, "scope_fee_product_class", scope.fee_product_class.value, "selection_fee_product_class", selection.fee_product_class.value )` |
| `RULE_BOOK_SCOPE_MISMATCH` | `( "market_fee_rule_book_hash", selection.market_fee_rule_book_hash, "stamp_duty_rule_book_hash", selection.stamp_duty_rule_book_hash, "scope_venue_id", scope.venue_id.value )` |
| `COMPONENT_REF_MISMATCH` | `( "market_fee_component_digest", selection.market_fee_component_ref.component_digest, "stamp_duty_component_digest", selection.stamp_duty_component_ref.component_digest )` |

### Order binding and authoritative queries

`bind_cn_a_share_fee_execution_v2(authority, order, /) -> CnAShareFeeExecutionBindingV2 | CnAShareFeeExecutionBindingFailureV2` is positional-only and performs no registry lookup. Binding fields/order are `authority`, `authority_hash`, `order`, `order_hash`, `order_id`, `account_id`, `venue_id`, `instrument_id`, `side`, `order_effective_at`; type is `cn_a_share_fee_execution_binding_v2`; `binding_hash` is derived. It derives all fields from exact Order and requires Account/Venue/Instrument/side and `coverage_from <= order.created_at.instant < coverage_to_exclusive` to match Scope.

Binding failure codes/order: `AUTHORITY_SCOPE_MISMATCH`, `ORDER_ACCOUNT_MISMATCH`, `ORDER_VENUE_MISMATCH`, `ORDER_INSTRUMENT_MISMATCH`, `ORDER_SIDE_MISMATCH`, `ORDER_CONTEXT_MISMATCH`. Failure fields/order are `authority`, `authority_hash`, `scope`, `scope_hash`, `order`, `order_hash`, `code`, `subject_ids`; type `cn_a_share_fee_execution_binding_failure_v2`. Prefix is `(code.value, authority_hash, scope_hash, order_hash)`. Exact suffixes are respectively `( "authority_scope_hash", authority.scope_hash, "authority_selection_hash", authority.selection_hash )`; `( "order_account_id", order.account_id, "scope_account_id", scope.account_id )`; `( "order_venue_id", order.intent.instrument_id.venue.value, "scope_venue_id", scope.venue_id.value )`; `( "order_instrument_id", str(order.intent.instrument_id), "scope_instrument_id", str(scope.instrument_id) )`; `( "order_side", order.intent.side.value, "allowed_order_sides_hash", canonical_sha256(scope.allowed_order_sides) )`; and `( "order_created_at_hash", canonical_sha256(order.created_at.instant), "scope_coverage_from_hash", canonical_sha256(scope.coverage_from), "scope_coverage_to_exclusive_hash", canonical_sha256(scope.coverage_to_exclusive), "scope_trade_mechanism", scope.trade_mechanism.value )`.

| code | exact binding-failure suffix |
| --- | --- |
| `AUTHORITY_SCOPE_MISMATCH` | `( "authority_scope_hash", authority.scope_hash, "authority_selection_hash", authority.selection_hash )` |
| `ORDER_ACCOUNT_MISMATCH` | `( "order_account_id", order.account_id, "scope_account_id", scope.account_id )` |
| `ORDER_VENUE_MISMATCH` | `( "order_venue_id", order.intent.instrument_id.venue.value, "scope_venue_id", scope.venue_id.value )` |
| `ORDER_INSTRUMENT_MISMATCH` | `( "order_instrument_id", str(order.intent.instrument_id), "scope_instrument_id", str(scope.instrument_id) )` |
| `ORDER_SIDE_MISMATCH` | `( "order_side", order.intent.side.value, "allowed_order_sides_hash", canonical_sha256(scope.allowed_order_sides) )` |
| `ORDER_CONTEXT_MISMATCH` | `( "order_created_at_hash", canonical_sha256(order.created_at.instant), "scope_coverage_from_hash", canonical_sha256(scope.coverage_from), "scope_coverage_to_exclusive_hash", canonical_sha256(scope.coverage_to_exclusive), "scope_trade_mechanism", scope.trade_mechanism.value )` |

`CnAShareCashFeeRuleQueryV2` fields/order are `authority`, `authority_hash`, `execution_binding`, `binding_hash`, `purpose`, `fill: Fill | None`, `fill_hash: str | None`, `fill_id: DomainId | None`; type `cn_a_share_cash_fee_rule_query_v2`. Its canonical body then derives `order_id`, `order_hash`, `account_id`, `venue_id`, `instrument_id`, `side`, `effective_at`; `query_hash` is derived. Only `CnAShareCashFeeRuleQueryV2.for_reservation(authority: CnAShareFeeExecutionAuthorityV2, execution_binding: CnAShareFeeExecutionBindingV2, /) -> CnAShareCashFeeRuleQueryV2 | CnAShareFeeQueryConstructionFailureV2` and `CnAShareCashFeeRuleQueryV2.for_final_fill(authority: CnAShareFeeExecutionAuthorityV2, execution_binding: CnAShareFeeExecutionBindingV2, fill: Fill | None, /) -> CnAShareCashFeeRuleQueryV2 | CnAShareFeeQueryConstructionFailureV2` construct semantic queries.

The constructor-derived `effective_at` is exact: RESERVATION uses `binding.order_effective_at`; FINAL_FILL uses `fill.execution_time`. Neither value is caller-supplied or inferred from another time.

Query failure codes/order are `AUTHORITY_BINDING_MISMATCH`, `RESERVATION_CONTEXT_MISMATCH`, `MISSING_FILL`, `FILL_ORDER_MISMATCH`, `FILL_ACCOUNT_MISMATCH`, `FILL_VENUE_MISMATCH`, `FILL_INSTRUMENT_MISMATCH`, `FILL_SIDE_MISMATCH`, `EXECUTION_TIME_MISMATCH`. The final constructor checks `MISSING_FILL` before dereference then requires exactly `binding.order_effective_at <= fill.execution_time < authority.scope.coverage_to_exclusive`. Failure fields/order are `authority`, `authority_hash`, `execution_binding`, `binding_hash`, `purpose`, `fill`, `fill_hash`, `code`, `subject_ids`; type `cn_a_share_fee_query_construction_failure_v2`. Prefix is `(code.value, authority_hash, binding_hash, purpose.value, fill_hash or "none")`; no subject tuple is deduplicated or sorted.

| code | exact suffix in order |
| --- | --- |
| `AUTHORITY_BINDING_MISMATCH` | `( "binding_authority_hash", execution_binding.authority_hash )` |
| `RESERVATION_CONTEXT_MISMATCH` | `( "order_id", execution_binding.order_id.value, "order_hash", execution_binding.order_hash, "order_effective_at_hash", canonical_sha256(execution_binding.order_effective_at) )` |
| `MISSING_FILL` | `( "fill", "none" )` |
| `FILL_ORDER_MISMATCH` | `( "fill_order_id", fill.order_id.value, "binding_order_id", execution_binding.order_id.value )` |
| `FILL_ACCOUNT_MISMATCH` | `( "fill_account_id", fill.account_id, "binding_account_id", execution_binding.account_id )` |
| `FILL_VENUE_MISMATCH` | `( "fill_venue_id", fill.venue_id.value, "binding_venue_id", execution_binding.venue_id.value )` |
| `FILL_INSTRUMENT_MISMATCH` | `( "fill_instrument_id", str(fill.instrument_id), "binding_instrument_id", str(execution_binding.instrument_id) )` |
| `FILL_SIDE_MISMATCH` | `( "fill_side", fill.side.value, "binding_side", execution_binding.side.value )` |
| `EXECUTION_TIME_MISMATCH` | `( "fill_execution_time_hash", canonical_sha256(fill.execution_time), "binding_order_effective_at_hash", canonical_sha256(execution_binding.order_effective_at), "scope_coverage_to_exclusive_hash", canonical_sha256(authority.scope.coverage_to_exclusive) )` |

### Books, policies, IDs, and results

`CnAShareMarketFeeBandV2` exact fields, in order, are:

1. `venue_id: VenueId`
2. `effective_from: UtcInstant`
3. `effective_to_exclusive: UtcInstant`
4. `handling_applies: bool`
5. `handling_rate: Rate`
6. `handling_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]`
7. `regulatory_applies: bool`
8. `regulatory_rate: Rate`
9. `regulatory_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]`
10. `chinaclear_transfer_applies: bool`
11. `chinaclear_transfer_rate: Rate`
12. `chinaclear_transfer_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]`
13. `hkscc_transfer_applies: bool`
14. `hkscc_transfer_rate: Rate`
15. `hkscc_transfer_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]`

Type is `cn_a_share_market_fee_band_v2`; `band_hash = canonical_sha256(body)`. The interval is finite, nonempty, half-open; each rate is a nonnegative `fee_fraction`; false applies requires exact zero rate; every source tuple is nonempty, canonical-sorted, and duplicate-free.

`CnAShareStampDutyBandV2` exact fields, in order, are `venue_id: VenueId`, `effective_from: UtcInstant`, `effective_to_exclusive: UtcInstant`, `applies_to_sell: bool`, `rate: Rate`, `source_refs: tuple[CnAShareFeeRuleSourceRef, ...]`. Type is `cn_a_share_stamp_duty_band_v2`; `band_hash` is derived; false sell applicability requires exact zero `fee_fraction` and source refs remain nonempty.

`CnAShareMarketFeeRuleBookV2` exact fields/order are `rule_book_key: str`, `rule_book_version: int`, `access_route: CnAShareExecutionAccessRoute`, `fee_product_class: CnAShareFeeProductClass`, `bands: tuple[CnAShareMarketFeeBandV2, ...]`; type is `cn_a_share_market_fee_rule_book_v2`. `CnAShareStampDutyRuleBookV2` exact fields/order are `rule_book_key: str`, `rule_book_version: int`, `access_route: CnAShareExecutionAccessRoute`, `fee_product_class: CnAShareFeeProductClass`, `bands: tuple[CnAShareStampDutyBandV2, ...]`; type is `cn_a_share_stamp_duty_rule_book_v2`. Both require version exactly 2, canonical Band order `(venue_id.value, effective_from, effective_to_exclusive, band_hash)`, and derive `rule_book_hash`.

The exact component bodies are:

```text
{
  type: "cn_a_share_cash_market_fee_component_v2", schema_version: 1,
  component_key: "equity.cn_a_share.cash.market-fees.route-product.v2",
  component_version: 2,
  algorithm_key: "cn-a-share-historical-market-fees-route-product-v2",
  rule_book_hash, access_route, fee_product_class, assessment_scale: 2,
  rounding: "half_up",
  quantization_version: "cn-a-share-market-fee.cny-cent.half-up.v2"
}
{
  type: "cn_a_share_cash_stamp_duty_component_v2", schema_version: 1,
  component_key: "equity.cn_a_share.cash.stamp-duty.route-product.v2",
  component_version: 2,
  algorithm_key: "cn-a-share-historical-stamp-duty-route-product-v2",
  rule_book_hash, access_route, fee_product_class, assessment_scale: 2,
  rounding: "half_up",
  quantization_version: "cn-a-share-stamp-duty.cny-cent.half-up.v2"
}
```

The resulting `ProfileComponentRef` has `port_type` respectively `FEE_ASSESSMENT_POLICY`/`TAX_POLICY`, the fixed key/version above, and `component_digest = canonical_sha256(component body)`.

`CnAShareCashMarketFeePolicyV2` exact fields/order are `authority: CnAShareFeeExecutionAuthorityV2`, `authority_hash: str`, `assessment_scale: Scale`; method is `assess_fees(query: CnAShareCashFeeRuleQueryV2, /) -> ProfilePortOutcome[CnAShareMarketFeeRuleResolutionV2, CnAShareFeeRuleFailureV2]`. `CnAShareCashStampDutyTaxPolicyV2` has exactly `authority: CnAShareFeeExecutionAuthorityV2`, `authority_hash: str`, `assessment_scale: Scale`; method is `assess_taxes(query: CnAShareCashFeeRuleQueryV2, /) -> ProfilePortOutcome[CnAShareStampDutyRuleResolutionV2, CnAShareFeeRuleFailureV2]`. Both require `Scale(2)` and exact Authority/hash equality.

Market charge keys/order are exactly `handling`, `securities_regulatory`, `chinaclear_transfer`, `hkscc_transfer`; tax key is exactly `stamp_duty`. Each generated generic rule uses this exact ID preimage:

```text
{
  type: "cn_a_share_fee_generated_rule_id_v2", schema_version: 1,
  rule_type, rule_schema_version: 1, component_key, component_version,
  component_digest, rule_book_hash, band_hash, authority_hash, binding_hash,
  query_hash, access_route, fee_product_class, charge_key, purpose, basis_type,
  applies, source_refs, quantization_version
}
```

`rule_type` is exactly `cn_a_share_market_fee_charge_rule_v2` or `cn_a_share_stamp_duty_charge_rule_v2`; tags are exactly `cn-a-share-market-fee-rule-v2` or `cn-a-share-stamp-duty-rule-v2`; every generated rule ID is exactly `f'{tag}:{canonical_sha256(preimage)}'`. Purpose wires are exactly `reservation`, `final_fill`, `final_order`; their basis-type wires are exactly `order_notional`, `fill`, `order` in that order. `final_order` is generated-rule purpose only, never `CnAShareFeeAssessmentPurposeV2`, and is always `NOT_APPLICABLE`. For market reservation/final-fill, applies is the selected charge Band bool; final-order uses false. For stamp reservation/final-fill, applies is exactly `(band.applies_to_sell and query.side is SELL)`; final-order uses false. True maps to `FeeReservationApplicability.APPLIES`/`FinalFeeApplicability.ALWAYS`; false maps to `NOT_APPLICABLE`, exact zero rate, and preserved nonempty refs.

`CnAShareMarketFeeRuleResolutionV2` exact fields/order are `authority: CnAShareFeeExecutionAuthorityV2`, `authority_hash: str`, `query: CnAShareCashFeeRuleQueryV2`, `query_hash: str`, `binding_hash: str`, `order_id: DomainId`, `order_hash: str`, `fill: Fill | None`, `fill_hash: str | None`, `fill_id: DomainId | None`, `side: OrderSide`, `effective_at: UtcInstant`, `active_band: CnAShareMarketFeeBandV2`, `active_band_hash: str`, `reservation_charge_rules: tuple[FeeReservationChargeRule, ...]`, `final_fill_charge_rules: tuple[FinalFeeChargeRule, ...]`, `final_order_not_applicable_rules: tuple[FinalFeeChargeRule, ...]`; type `cn_a_share_market_fee_rule_resolution_v2`. Every market tuple has four rules in fixed charge order.

`CnAShareStampDutyRuleResolutionV2` exact fields/order are `authority: CnAShareFeeExecutionAuthorityV2`, `authority_hash: str`, `query: CnAShareCashFeeRuleQueryV2`, `query_hash: str`, `binding_hash: str`, `order_id: DomainId`, `order_hash: str`, `fill: Fill | None`, `fill_hash: str | None`, `fill_id: DomainId | None`, `side: OrderSide`, `effective_at: UtcInstant`, `active_band: CnAShareStampDutyBandV2`, `active_band_hash: str`, `reservation_charge_rule: FeeReservationChargeRule`, `final_fill_charge_rule: FinalFeeChargeRule`, `final_order_not_applicable_rule: FinalFeeChargeRule`; type `cn_a_share_stamp_duty_rule_resolution_v2`. Both resolutions derive `resolution_hash` over every listed field and reconstruct all query provenance.

Policy failure prefix is exactly `(code.value, policy.authority_hash, query.query_hash)`; no subject tuple is deduplicated or sorted. Codes/order are `EXECUTION_AUTHORITY_MISMATCH`, `QUERY_PROVENANCE_MISMATCH`, `RULE_BOOK_SCOPE_MISMATCH`, `MISSING_RULE_INTERVAL`, `OVERLAPPING_RULE_INTERVALS`. `EXECUTION_AUTHORITY_MISMATCH` compares exact query/policy Authority/hash. Canonical-equivalent direct construction is accepted: `QUERY_PROVENANCE_MISMATCH` means only that re-running the authoritative constructor from purpose, Authority, binding and Fill does not produce an exactly equal query/hash. Thus mismatched `dataclasses.replace`/`object.__new__` controls fail provenance; direct construction with canonical-equivalent body does not.

| code | exact suffix in order |
| --- | --- |
| `EXECUTION_AUTHORITY_MISMATCH` | `( "query_authority_hash", query.authority_hash, "policy_authority_hash", policy.authority_hash, "query_scope_hash", query.authority.scope_hash, "policy_scope_hash", policy.authority.scope_hash )` |
| `QUERY_PROVENANCE_MISMATCH` | `( "purpose", query.purpose.value, "reconstructed_query_hash", reconstructed.query_hash )` on successful reconstruction; otherwise `( "purpose", query.purpose.value, "query_construction_failure_hash", reconstruction_failure.failure_hash )` |
| `RULE_BOOK_SCOPE_MISMATCH` | `( "scope_hash", query.authority.scope_hash, "market_fee_rule_book_hash", query.authority.market_fee_rule_book_hash, "stamp_duty_rule_book_hash", query.authority.stamp_duty_rule_book_hash )` |
| `MISSING_RULE_INTERVAL` | `( "venue_id", query.venue_id.value, "effective_at_hash", canonical_sha256(query.effective_at), "rule_book_hash", selected_rule_book.rule_book_hash, "active_band_hashes_hash", canonical_sha256(()) )` |
| `OVERLAPPING_RULE_INTERVALS` | `( "venue_id", query.venue_id.value, "effective_at_hash", canonical_sha256(query.effective_at), "rule_book_hash", selected_rule_book.rule_book_hash, "active_band_hashes_hash", canonical_sha256(tuple(sorted(band.band_hash for band in active_bands))) )` |

`CnAShareFeeRuleFailureCodeV2` exact declaration order and wire values are:

```python
class CnAShareFeeRuleFailureCodeV2(str, Enum):
    EXECUTION_AUTHORITY_MISMATCH = "execution_authority_mismatch"
    QUERY_PROVENANCE_MISMATCH = "query_provenance_mismatch"
    RULE_BOOK_SCOPE_MISMATCH = "rule_book_scope_mismatch"
    MISSING_RULE_INTERVAL = "missing_rule_interval"
    OVERLAPPING_RULE_INTERVALS = "overlapping_rule_intervals"
```

`CnAShareFeeRuleFailureV2` exact fields/order are `query: CnAShareCashFeeRuleQueryV2`, `query_hash: str`, `code: CnAShareFeeRuleFailureCodeV2`, `subject_ids: tuple[str, ...]`. Its canonical body is exactly `{type: "cn_a_share_fee_rule_failure_v2", schema_version: 1, query, query_hash, code: code.value, subject_ids}`; `failure_hash = canonical_sha256(body)`. Constructor requires `query_hash == query.query_hash`, exact enum type, and the code-specific subject tuple above.

`CnAShareFeeReservationBufferV2` exact fields/order are `market_resolution: CnAShareMarketFeeRuleResolutionV2`, `tax_resolution: CnAShareStampDutyRuleResolutionV2`, `maximum_fill_count: int`, `market_charge_rule: FeeReservationChargeRule`, `tax_charge_rule: FeeReservationChargeRule`; type `cn_a_share_fee_reservation_buffer_v2`; `buffer_hash` derived. `create` requires both resolutions to have exact same Authority/hash, query/hash, binding hash, order ID/hash, Fill/fill hash/fill ID provenance, side, effective time, and `query.purpose is RESERVATION`; any mismatch raises exactly `ValueError("reservation buffer resolution context mismatch")`. Its exact API is:

```python
CnAShareFeeReservationBufferV2.create(*, market_resolution, tax_resolution, maximum_fill_count)
CnAShareFeeReservationBufferV2.covers_fill_count(self, fill_count: int, /) -> bool
CnAShareFeeReservationBufferV2.require_covers_fills(self, fills: tuple[Fill, ...], /) -> None
```

`maximum_fill_count` is positive; `covers_fill_count` rejects non-int/bool/negative and returns `fill_count <= maximum_fill_count`; `require_covers_fills` rejects non-tuple/non-Fill items and raises `ValueError("actual fill count exceeds reservation bound")` above the bound, exactly equivalent to v1 over-bound behavior. With `u=floor(maximum_fill_count/2)`, component count is applicable charges only; amount is `Money(component_count * u, Scale(2), "CNY")`; zero count is NOT_APPLICABLE and `Money(0, Scale(2), "CNY")`.

The buffer rule-ID preimage is exactly:

```text
{
  type: "cn_a_share_fee_reservation_buffer_rule_id_v2", schema_version: 1,
  rule_type: "cn_a_share_fee_reservation_buffer_rule_v2",
  rule_schema_version: 1, component_key, component_version, component_digest,
  authority_hash, scope_hash, binding_hash, market_resolution_hash,
  tax_resolution_hash, maximum_fill_count, component_count, applies, charge_key,
  basis_type: "flat_per_order",
  amount: Money(component_count * floor(maximum_fill_count / 2), Scale(2), "CNY"),
  quantization_version: "cn-a-share-fee-reservation-buffer.cny-cent.half-up.v2"
}
```

Buffer tag is exactly `cn-a-share-fee-reservation-buffer-rule-v2`; each buffer ID is exactly `f'{tag}:{canonical_sha256(preimage)}'`. Market buffer uses `charge_key="handling"`; tax buffer uses `charge_key="stamp_duty"`; `applies == (component_count > 0)`. Domestic ordinary market count is 3; separately evidenced Northbound ordinary can be 4.

### XSHE compatibility projection

The exact positional-only API is:

```python
project_cn_a_share_domestic_ordinary_fee_rules_v2(
    market_rule_book: CnAShareMarketFeeRuleBook,
    stamp_duty_rule_book: CnAShareStampDutyRuleBook,
    /,
) -> CnAShareDomesticOrdinaryFeeProjectionV2 | CnAShareDomesticOrdinaryFeeProjectionFailureV2
```

`CnAShareDomesticOrdinaryFeeProjectionV2` exact fields/order are `algorithm_id: str`, `source_market_rule_book: CnAShareMarketFeeRuleBook`, `source_market_rule_book_hash: str`, `source_stamp_duty_rule_book: CnAShareStampDutyRuleBook`, `source_stamp_duty_rule_book_hash: str`, `access_route: CnAShareExecutionAccessRoute`, `fee_product_class: CnAShareFeeProductClass`, `market_fee_rule_book: CnAShareMarketFeeRuleBookV2`, `market_fee_rule_book_hash: str`, `stamp_duty_rule_book: CnAShareStampDutyRuleBookV2`, `stamp_duty_rule_book_hash: str`; type `cn_a_share_domestic_ordinary_fee_projection_v2`; fixed algorithm ID `cn-a-share-domestic-ordinary-v1-to-v2-fee-projection-v1`; `projection_hash` derived.

Output keys are exactly `equity.cn_a_share.cash.market-fees.domestic.ordinary-a-share.projected-v2` and `equity.cn_a_share.cash.stamp-duty.domestic.ordinary-a-share.projected-v2`; both have `rule_book_version=2`, route `DOMESTIC`, product `ORDINARY_A_SHARE`, and only XSHE Bands. Every v1 market/tax source Band maps interval/rate/source economics without extension/coalescing/reinterpretation: handling→handling, regulatory→regulatory, transfer→ChinaClear, stamp→stamp duty. HKSCC uses `applies=False`, zero rate, and exactly one ref:

```text
CnAShareFeeRuleSourceRef(
  source_key="cn-a-share-domestic-ordinary-v1-to-v2-hkscc-not-applicable",
  source_hash=canonical_sha256({
    type: "cn_a_share_fee_compatibility_hkscc_source_v2", schema_version: 1,
    source_market_rule_book_hash, source_stamp_duty_rule_book_hash,
    venue_id: "xshe", effective_from, effective_to_exclusive,
    access_route: "domestic", fee_product_class: "ordinary_a_share",
    charge_key: "hkscc_transfer", applies: false
  })
)
```

`CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2` exact first-applicable order is `NON_XSHE_MARKET_SOURCE`, `NON_XSHE_STAMP_DUTY_SOURCE`, `MARKET_SOURCE_INTERVAL_INVALID`, `STAMP_DUTY_SOURCE_INTERVAL_INVALID`, `MARKET_SOURCE_ECONOMIC_INVALID`, `STAMP_DUTY_SOURCE_ECONOMIC_INVALID`.

`CnAShareDomesticOrdinaryFeeProjectionFailureV2` exact fields/order are `market_rule_book: CnAShareMarketFeeRuleBook`, `market_rule_book_hash: str`, `stamp_duty_rule_book: CnAShareStampDutyRuleBook`, `stamp_duty_rule_book_hash: str`, `code: CnAShareDomesticOrdinaryFeeProjectionFailureCodeV2`, `subject_ids: tuple[str, ...]`; type `cn_a_share_domestic_ordinary_fee_projection_failure_v2`; `failure_hash` derived. Prefix is exactly `(code.value, market_rule_book_hash, stamp_duty_rule_book_hash)`; no subject tuple is deduplicated or sorted.

| code | exact suffix in order |
| --- | --- |
| `NON_XSHE_MARKET_SOURCE` | `( "venue_id", first_non_xshe_market_band.venue_id.value, "band_hash", first_non_xshe_market_band.band_hash )` |
| `NON_XSHE_STAMP_DUTY_SOURCE` | `( "venue_id", first_non_xshe_stamp_band.venue_id.value, "band_hash", first_non_xshe_stamp_band.band_hash )` |
| `MARKET_SOURCE_INTERVAL_INVALID` | `( "band_hash", first_invalid_market_band.band_hash, "effective_from_hash", canonical_sha256(first_invalid_market_band.effective_from), "effective_to_exclusive_hash", canonical_sha256(first_invalid_market_band.effective_to_exclusive) )` |
| `STAMP_DUTY_SOURCE_INTERVAL_INVALID` | `( "band_hash", first_invalid_stamp_band.band_hash, "effective_from_hash", canonical_sha256(first_invalid_stamp_band.effective_from), "effective_to_exclusive_hash", canonical_sha256(first_invalid_stamp_band.effective_to_exclusive) )` |
| `MARKET_SOURCE_ECONOMIC_INVALID` | `( "band_hash", first_invalid_market_band.band_hash, "economic_hash", canonical_sha256(first_invalid_market_band) )` |
| `STAMP_DUTY_SOURCE_ECONOMIC_INVALID` | `( "band_hash", first_invalid_stamp_band.band_hash, "economic_hash", canonical_sha256(first_invalid_stamp_band) )` |

The `first_*` value is the first source Band in v1 canonical Band order satisfying the named predicate. All failure paths return no partial output. Projection remains a finite compatibility proof only: no July-2026 evidence, Runtime selection, provider qualification, or open-ended continuity.

## RED and acceptance for A

After the parent Acceptance Matrix registers V2A `READY`, add only kernel contract/golden/architecture tests and kernel fixture. Test exact field/signature/type/order, all failure precedence/subjects, missing Fill, lower/upper execution time, direct/replace/object-new provenance, separate ChinaClear/HKSCC, all applies mappings, buffer count/Money/IDs, XSHE rejection, empty source rejection, projection identities, import boundary, and all protected v1 bytes. V2A passes only focused Kernel tests, v1 regression/byte locks, static import check, mypy, gitleaks, diff/status, and independent review. It creates no Runtime or Semantic Run claim.

## Nonclaims

No Runtime profile selection, resolved-profile proof, profile/build identity, registration, ExecutionCase, Semantic Run, provider completeness, July-2026 closure, decision grade, live use, or deployment authorization is frozen here.
