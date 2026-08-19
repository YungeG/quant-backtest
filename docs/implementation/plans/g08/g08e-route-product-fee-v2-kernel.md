---
id: G08E-ROUTE-PRODUCT-FEE-V2A
readiness: READY_FOR_CONTRACT_RED
gate_status: DRAFT
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

`READY_FOR_CONTRACT_RED`. This is a pure Kernel contract. It does not import Runtime, resolved profiles, profile registries, profile/build manifests, `ExecutionCaseSemanticSpec`, Financial Dispatch, Runner, or Semantic Run. Runtime selection and semantic binding are exclusively deferred to [V2B](g08e-route-product-fee-v2-runtime-binding.md).

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

Append the declared v2 names to `crypto_quant_trading.profiles.cn_a_share.__all__` after every frozen v1 member; do not export them from `crypto_quant_trading` root. The module imports stdlib, `crypto_quant_domain`, existing generic fee/reservation/port contracts, and v1 A-share fee types only for projection. It performs no I/O and imports no Runtime, Builder, provider, filesystem, network, database, process, wall clock, dynamic loader, or test support.

All v2 dataclasses are frozen/slotted. Every v2 canonical body has `schema_version: 1`, fixed `_v2` type literal, declared field order, and a derived hash excluded from its preimage. Constructors enforce exact primitive/concrete/canonical structure only; semantic operations return the first structured failure. No field or parameter has a default.

Append exactly these names after the frozen v1 `__all__` sequence: `CnAShareExecutionAccessRoute`, `CnAShareFeeProductClass`, `CnAShareFeeAssessmentPurposeV2`, `CnAShareFeeExecutionScopeV2`, `CnAShareFeeExecutionSelectionV2`, `CnAShareFeeExecutionAuthorityV2`, `CnAShareFeeExecutionAuthorityFailureCodeV2`, `CnAShareFeeExecutionAuthorityFailureV2`, `CnAShareFeeExecutionBindingV2`, `CnAShareFeeExecutionBindingFailureCodeV2`, `CnAShareFeeExecutionBindingFailureV2`, `CnAShareCashFeeRuleQueryV2`, `CnAShareFeeQueryConstructionFailureCodeV2`, `CnAShareFeeQueryConstructionFailureV2`, `CnAShareMarketFeeBandV2`, `CnAShareMarketFeeRuleBookV2`, `CnAShareStampDutyBandV2`, `CnAShareStampDutyRuleBookV2`, `CnAShareMarketFeeRuleResolutionV2`, `CnAShareStampDutyRuleResolutionV2`, `CnAShareFeeRuleFailureCodeV2`, `CnAShareFeeRuleFailureV2`, `CnAShareCashMarketFeePolicyV2`, `CnAShareCashStampDutyTaxPolicyV2`, `CnAShareFeeReservationBufferV2`, `CnAShareDomesticOrdinaryFeeProjectionV2`, `bind_cn_a_share_fee_execution_v2`, and `project_cn_a_share_domestic_ordinary_fee_rules_v2`.

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

Canonical type is `cn_a_share_fee_execution_scope_v2`; `scope_hash = canonical_sha256(body)`. Structure requires exact nested identities, finite half-open coverage, canonical unique side tuple, and no inferred route/product. Caller selection of this value is owned by V2B.

`CnAShareFeeExecutionSelectionV2` fields/order are `selection_key: str`, `selection_version: int`, `access_route`, `fee_product_class`, `market_fee_rule_book: CnAShareMarketFeeRuleBookV2`, `market_fee_rule_book_hash: str`, `stamp_duty_rule_book: CnAShareStampDutyRuleBookV2`, `stamp_duty_rule_book_hash: str`, `market_fee_component_ref: ProfileComponentRef`, `stamp_duty_component_ref: ProfileComponentRef`. Its type is `cn_a_share_fee_execution_selection_v2`; `selection_hash` is derived.

`CnAShareFeeExecutionAuthorityV2` is pure Kernel selection, not profile provenance. Fields/order are `authority_key: str`, `authority_version: int`, `scope`, `scope_hash`, `selection`, `selection_hash`, `access_route`, `fee_product_class`, `market_fee_rule_book`, `market_fee_rule_book_hash`, `stamp_duty_rule_book`, `stamp_duty_rule_book_hash`, `market_fee_component_ref`, `stamp_duty_component_ref`. Type is `cn_a_share_fee_execution_authority_v2`; `authority_version == 2`; `authority_hash` is derived. The pure authority constructor validates Scope/Selection equality, exact book/hash/ref equality, route/product equality, and no interchangeable market/stamp book pair.

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

`CnAShareCashFeeRuleQueryV2` fields/order are `authority`, `authority_hash`, `execution_binding`, `binding_hash`, `purpose`, `fill: Fill | None`, `fill_hash: str | None`, `fill_id: DomainId | None`; type `cn_a_share_cash_fee_rule_query_v2`. Its canonical body then derives `order_id`, `order_hash`, `account_id`, `venue_id`, `instrument_id`, `side`, `effective_at`; `query_hash` is derived. Only `for_reservation(authority, execution_binding, /)` and `for_final_fill(authority, execution_binding, fill, /)` construct semantic queries.

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

`CnAShareMarketFeeBandV2` fields/order are `venue_id`, `effective_from`, `effective_to_exclusive`, handling applies/rate/source refs, regulatory applies/rate/source refs, ChinaClear applies/rate/source refs, HKSCC applies/rate/source refs; type `cn_a_share_market_fee_band_v2`. `CnAShareStampDutyBandV2` fields/order are `venue_id`, interval, `applies_to_sell`, `rate`, `source_refs`; type `cn_a_share_stamp_duty_band_v2`. All intervals are finite half-open, rates are nonnegative `fee_fraction`, false applies has exact zero rate, and every canonical source-ref tuple is nonempty/sorted/duplicate-free.

Market and stamp RuleBooks each have fields/order `rule_book_key`, `rule_book_version`, `access_route`, `fee_product_class`, `bands`; types `cn_a_share_market_fee_rule_book_v2` and `cn_a_share_stamp_duty_rule_book_v2`; version is exactly 2. The four market charge keys/order are exactly `handling`, `securities_regulatory`, `chinaclear_transfer`, `hkscc_transfer`; tax key is exactly `stamp_duty`. ChinaClear and HKSCC never share a ref or rule ID.

Policy fields/order are `authority: CnAShareFeeExecutionAuthorityV2`, `authority_hash: str`, `assessment_scale: Scale`. Component preimages use types `cn_a_share_cash_market_fee_component_v2` and `cn_a_share_cash_stamp_duty_component_v2`, component keys/versions `equity.cn_a_share.cash.market-fees.route-product.v2`/2 and `equity.cn_a_share.cash.stamp-duty.route-product.v2`/2, fixed algorithm and CNY-cent half-up v2 quantization keys, RuleBook hash, route/product and scale. `ProfileComponentRef.component_digest` is canonical SHA-256 of the applicable preimage.

For every generated generic rule, ID preimage is exact:

```text
{
 type: "cn_a_share_fee_generated_rule_id_v2", schema_version: 1,
 rule_type, rule_schema_version: 1, component_key, component_version,
 component_digest, rule_book_hash, band_hash, authority_hash, binding_hash,
 query_hash, access_route, fee_product_class, charge_key, purpose, basis_type,
 applies, source_refs, quantization_version
}
```

`rule_type` is `cn_a_share_market_fee_charge_rule_v2` or `cn_a_share_stamp_duty_charge_rule_v2`; tags are `cn-a-share-market-fee-rule-v2` or `cn-a-share-stamp-duty-rule-v2`. Reservation/final-fill applies uses the selected Band (stamp additionally requires SELL); final-order is false. False maps to `NOT_APPLICABLE`, zero rate, and preserved nonempty ref.

Policy failure prefix is exactly `(code.value, policy.authority_hash, query.query_hash)`; no subject tuple is deduplicated or sorted. Codes/order are `EXECUTION_AUTHORITY_MISMATCH`, `QUERY_PROVENANCE_MISMATCH`, `AUTHORITY_QUERY_MISMATCH`, `RULE_BOOK_SCOPE_MISMATCH`, `MISSING_RULE_INTERVAL`, `OVERLAPPING_RULE_INTERVALS`. `EXECUTION_AUTHORITY_MISMATCH` compares query Authority/hash to policy Authority/hash. Policy then re-runs the canonical constructor by purpose and requires exact query/hash equality; direct `FINAL_FILL(fill=None)`, direct construction, `dataclasses.replace`, and `object.__new__` bypass yield `QUERY_PROVENANCE_MISMATCH`.

| code | exact suffix in order |
| --- | --- |
| `EXECUTION_AUTHORITY_MISMATCH` | `( "query_authority_hash", query.authority_hash, "policy_authority_hash", policy.authority_hash, "query_scope_hash", query.authority.scope_hash, "policy_scope_hash", policy.authority.scope_hash )` |
| `QUERY_PROVENANCE_MISMATCH` | `( "purpose", query.purpose.value, "reconstructed_query_hash", reconstructed.query_hash )` on successful reconstruction; otherwise `( "purpose", query.purpose.value, "query_construction_failure_hash", reconstruction_failure.failure_hash )` |
| `AUTHORITY_QUERY_MISMATCH` | `( "query_authority_hash", query.authority_hash, "policy_authority_hash", policy.authority_hash )` |
| `RULE_BOOK_SCOPE_MISMATCH` | `( "scope_hash", query.authority.scope_hash, "market_fee_rule_book_hash", query.authority.market_fee_rule_book_hash, "stamp_duty_rule_book_hash", query.authority.stamp_duty_rule_book_hash )` |
| `MISSING_RULE_INTERVAL` | `( "venue_id", query.venue_id.value, "effective_at_hash", canonical_sha256(query.effective_at), "rule_book_hash", selected_rule_book.rule_book_hash, "active_band_hashes_hash", canonical_sha256(()) )` |
| `OVERLAPPING_RULE_INTERVALS` | `( "venue_id", query.venue_id.value, "effective_at_hash", canonical_sha256(query.effective_at), "rule_book_hash", selected_rule_book.rule_book_hash, "active_band_hashes_hash", canonical_sha256(tuple(sorted(band.band_hash for band in active_bands))) )` |

`reconstructed`, `reconstruction_failure`, `selected_rule_book`, and `active_bands` are prescribed local values, never caller-selected IDs. Labels are literal strings; enums/Venue use `.value`; hashes are canonical `sha256:` text. Therefore every policy failure hash is uniquely reproducible.

Market resolution fields/order are Authority/query hashes, binding/order/fill provenance, side/effective time, active Band/hash, four reservation rules, four final Fill rules, four final Order not-applicable rules; type `cn_a_share_market_fee_rule_resolution_v2`. Stamp resolution is the analogous one-rule type `cn_a_share_stamp_duty_rule_resolution_v2`. Both resolution hashes bind every listed field.

`CnAShareFeeReservationBufferV2` fields/order are market resolution, tax resolution, `maximum_fill_count`, market rule, tax rule; type `cn_a_share_fee_reservation_buffer_v2`. With `u=floor(maximum_fill_count/2)`, component count is applicable charges only; amount is `Money(component_count * u, Scale(2), "CNY")`; zero count is NOT_APPLICABLE and `Money(0, Scale(2), "CNY")`. Buffer ID preimage type is `cn_a_share_fee_reservation_buffer_rule_id_v2`, includes component/Authority/Scope/binding/resolution hashes, count/applies/key, exact Money and fixed buffer quantization. Domestic ordinary market count is 3; separately evidenced Northbound ordinary can be 4.

### XSHE compatibility projection

`project_cn_a_share_domestic_ordinary_fee_rules_v2(market_rule_book, stamp_duty_rule_book, /)` is the only projection. It rejects every source Band whose `venue_id != VenueId("xshe")` before output, never filters XSHG silently, preserves finite intervals/economics, maps v1 transfer only to ChinaClear, and creates HKSCC false/zero with one nonempty deterministic `cn_a_share_fee_compatibility_hkscc_source_v2` ref. Output keys are the domestic ordinary projected-v2 keys, version 2, XSHE only. Projection type is `cn_a_share_domestic_ordinary_fee_projection_v2`; it never proves July-2026 evidence or Runtime selection.

## RED and acceptance for A

Add only kernel contract/golden/architecture tests and kernel fixture after approval. Test exact field/signature/type/order, all failure precedence/subjects, missing Fill, lower/upper execution time, direct/replace/object-new provenance, separate ChinaClear/HKSCC, all applies mappings, buffer count/Money/IDs, XSHE rejection, empty source rejection, projection identities, import boundary, and all protected v1 bytes. V2A passes only focused Kernel tests, v1 regression/byte locks, static import check, mypy, gitleaks, diff/status, and independent review. It creates no Runtime or Semantic Run claim.

## Nonclaims

No Runtime profile selection, resolved-profile proof, profile/build identity, registration, ExecutionCase, Semantic Run, provider completeness, July-2026 closure, decision grade, live use, or deployment authorization is frozen here.
