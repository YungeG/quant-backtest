---
id: G08E-ROUTE-PRODUCT-FEE-V2
readiness: READY_FOR_CONTRACT_RED
gate_status: DRAFT
owner: trading-kernel concrete A-share fee policy + additive Runtime binding
produces:
  - route/product-aware A-share execution-fee v2 contract
  - finite domestic ordinary-A-share v1-to-v2 compatibility projection
  - immutable profile/order execution binding
consumes:
  - immutable G08E v1 fee/tax contracts and fixture
  - immutable G08H v1 resolved-profile contracts and fixture
  - ADR 0005 route/product decision
  - G12H F1 blocker report
depends_on:
  contract: [G08E, G08H]
  evidence: [ADR-0005]
  write_conflict: [kernel-cn-a-share-fee-tax, runtime-cn-a-share-profile-binding]
fan_out: [G12H-EFFECTIVE-UNTIL-SUPERSEDED-V2]
---

# G08E Route/Product-aware China A-share Execution Fee v2

## Status

`READY_FOR_CONTRACT_RED` only. [ADR 0005](../../../adr/0005-cn-a-share-fees-require-access-route-and-product-class.md) accepts the additive contract. No code, fixture, registry, Acceptance Matrix, README, G12 publication, or qualification change is authorized by this plan freeze.

The implementation contract is not `PASSED`. G12H F1 remains blocked until the complete authority, private profile-binding seam, Order/Fill constructors, and both v2 policies pass compatibility, semantic, architecture, and byte-lock acceptance. That acceptance is independent of G12H: it uses only the finite XSHE v1-to-v2 compatibility projection.

## Goal and first enforceable scope

Make execution access route and fee product class explicit, immutable, and enforceable at every A-share reservation/final fee query without changing any v1 identity.

The first success scope is exactly:

```text
execution_access_route: DOMESTIC
fee_product_class: ORDINARY_A_SHARE
venue_id: XSHE
instrument_type: InstrumentType.EQUITY
quote_currency_id: CNY
settlement_currency_id: CNY
trade_mechanism: AUCTION
basis: trade_notional
```

The enum domain also names `NORTHBOUND_STOCK_CONNECT`, `PREFERRED_STOCK`, and `ETF`, but those combinations do not inherit domestic ordinary economics. They require separate evidence, v2 RuleBooks, and a profile binding capable of proving the selected combination.

## Frozen compatibility boundary

The following remain exact:

- every public v1 symbol and signature in `commission_tax.py`;
- `CnAShareCashFeeRuleQuery` field order and canonical body;
- all v1 Band, RuleBook, resolution, failure, buffer, component, generated-rule, RuleSet, assessment, Journal, and profile identities;
- `CnAShareProfileCompositionRequest`, all G08H declarations/results, `CnAShareProfileComposer.compose(request, /)`, and existing test-support builder signatures;
- all accepted v1 fixture bytes and hashes;
- the existing `equity.cn_a_share.v1` profile and root exports.

No v1 class gains a field, default, alias, overload, branch, schema change, or route/product interpretation. V2 never calls v1 policy methods and then relabels their result. It may only copy finite v1 source economics through the explicit compatibility projection below.

Protected raw fixture SHA-256 values are:

```text
3ef26743bc9cebfe546f77812c6773cbdf3353e0337d03ed512d5f1c396f702b  tests/fixtures/kernel/profiles/cn_a_share/commission-tax-v1.json
aa032668a5207b61b6c8815894e0087f1c1e734d41e9707c7d32111b6c1cd79f  tests/fixtures/runtime/profiles/cn-a-share-resolved-profile-composition-v1.json
08358c1c0d2144fb23c1b1c8862fa6c879bd285533e5fa415e5cc0273013e905  tests/fixtures/runtime/engine/cn-a-share-resolved-profile-development-journey-v1.json
19017a07fbfd2da954483648fb168d87212f88e92fccca7c28fb0a514b202515  tests/fixtures/market_data/rule_authorities/cn-a-share-development-v1/declaration.json
7a95188cf05d401fcaed80b548f82f22f0b9bc23f6423c6ff1190de775291f7d  tests/fixtures/market_data/rule_authorities/cn-a-share-development-v1/publication.expected.json
```

## Minimal deep seam

### Production files

Add exactly two production modules:

```text
packages/trading-kernel/src/crypto_quant_trading/profiles/cn_a_share/commission_tax_v2.py
packages/backtest-runtime/src/crypto_quant_backtest/cn_a_share_fee_v2.py
```

Update only the concrete A-share submodule export file:

```text
packages/trading-kernel/src/crypto_quant_trading/profiles/cn_a_share/__init__.py
```

Do not modify `commission_tax.py`, `cn_a_share_profile.py`, generic fee/tax ports, generic fee arithmetic, Engine, Runner, Dispatcher, Journal, Ledger, profile registry, Runtime root exports, Builder, or market-data packages.

`commission_tax_v2.py` may import stdlib, `crypto_quant_domain`, existing generic fee/reservation/port contracts, and the v1 A-share fee types needed by the compatibility projection. It performs no I/O and imports no Runtime, Builder, provider, repository, filesystem, network, database, process, wall clock, dynamic loader, or test code.

`cn_a_share_fee_v2.py` is the private pure profile-authority binding seam. It may import v1 `CnAShareResolvedProfile` and the v2 Kernel selection/authority types, and contains only `_create_cn_a_share_fee_execution_authority_v2(resolved_profile, selection, /)`. It imports no Engine, Runner, Builder, provider, repository, filesystem, network, database, process, wall clock, callback, or implementation object identity. It is not imported or exported by `crypto_quant_backtest.__init__`.

### Test/support files after RED is approved

Use additive files only:

```text
tests/kernel/profiles/cn_a_share/test_commission_tax_v2_contract.py
tests/kernel/profiles/cn_a_share/test_commission_tax_v2_golden.py
tests/runtime/profiles/cn_a_share/test_fee_execution_binding_v2.py
tests/architecture/test_g08e_route_product_fee_v2_boundary.py
tests/support/cn_a_share/route_product_fee_v2.py
tests/fixtures/kernel/profiles/cn_a_share/route-product-fee-v2.json
tests/fixtures/runtime/profiles/cn-a-share-fee-execution-binding-v2.json
```

Do not edit existing v1 fixtures or `tests/support/cn_a_share/__init__.py`.

## Exact additive public contract

All v2 values are frozen, slotted dataclasses. Every v2 canonical body has `schema_version: 1`, a fixed type literal ending `_v2`, fields in the declared order below, and a derived hash excluded from its own preimage. A constructor rejects wrong exact types, noncanonical text/hash, supplied derived-hash forgery, invalid version/scale, non-finite intervals, duplicate source refs, or wrong canonical reconstruction. A policy returns the structured first semantic failure and no partial result. No v2 argument or field has a default.

### Public surface

Only `crypto_quant_trading.profiles.cn_a_share` exposes these additive names, in exactly this appended order:

```text
CnAShareExecutionAccessRoute
CnAShareFeeProductClass
CnAShareFeeAssessmentPurposeV2
CnAShareFeeExecutionSelectionV2
CnAShareFeeExecutionAuthorityV2
CnAShareFeeExecutionBindingV2
CnAShareCashFeeRuleQueryV2
CnAShareMarketFeeBandV2
CnAShareMarketFeeRuleBookV2
CnAShareStampDutyBandV2
CnAShareStampDutyRuleBookV2
CnAShareMarketFeeRuleResolutionV2
CnAShareStampDutyRuleResolutionV2
CnAShareFeeRuleFailureCodeV2
CnAShareFeeRuleFailureV2
CnAShareCashMarketFeePolicyV2
CnAShareCashStampDutyTaxPolicyV2
CnAShareFeeReservationBufferV2
CnAShareDomesticOrdinaryFeeProjectionV2
bind_cn_a_share_fee_execution_v2
project_cn_a_share_domestic_ordinary_fee_rules_v2
```

The existing `cn_a_share.__all__` members and their order are frozen byte-for-byte; the list above is appended after the final existing v1 member in this order. No v2 name is exported from `crypto_quant_trading`, `crypto_quant_backtest`, or another package root.

### Enums

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

The member order and values are exact. `InstrumentType.EQUITY`, symbol, stable key, board, account permission, and current metadata never infer either route/product enum.

### Selection and profile-bound fee authority

`CnAShareFeeExecutionSelectionV2` is the explicit immutable build input. Its exact fields, in order, are:

1. `selection_key: str`
2. `selection_version: int`
3. `access_route: CnAShareExecutionAccessRoute`
4. `fee_product_class: CnAShareFeeProductClass`
5. `market_fee_rule_book: CnAShareMarketFeeRuleBookV2`
6. `market_fee_rule_book_hash: str`
7. `stamp_duty_rule_book: CnAShareStampDutyRuleBookV2`
8. `stamp_duty_rule_book_hash: str`
9. `market_fee_component_ref: ProfileComponentRef`
10. `stamp_duty_component_ref: ProfileComponentRef`

Its canonical body is `cn_a_share_fee_execution_selection_v2`; `selection_hash = canonical_sha256(body)`. It requires `selection_version == 1`, exact equality of both book scopes to the two enum fields, both book hashes to their complete book bodies, and both refs to the exact v2 component preimages below.

`CnAShareFeeExecutionAuthorityV2` is the only authority accepted by v2 policies. Its exact fields, in order, are:

1. `resolved_profile_digest: str`
2. `profile_composition_request_hash: str`
3. `market_profile_key: str`
4. `market_profile_version: int`
5. `market_profile_digest: str`
6. `execution_account_profile_key: str`
7. `execution_account_profile_version: int`
8. `execution_account_profile_digest: str`
9. `instrument_scope_declaration_hash: str`
10. `account_scope_declaration_hash: str`
11. `selection: CnAShareFeeExecutionSelectionV2`
12. `selection_hash: str`
13. `access_route: CnAShareExecutionAccessRoute`
14. `fee_product_class: CnAShareFeeProductClass`
15. `market_fee_rule_book: CnAShareMarketFeeRuleBookV2`
16. `market_fee_rule_book_hash: str`
17. `stamp_duty_rule_book: CnAShareStampDutyRuleBookV2`
18. `stamp_duty_rule_book_hash: str`
19. `market_fee_component_ref: ProfileComponentRef`
20. `stamp_duty_component_ref: ProfileComponentRef`

Its canonical body is exactly:

```text
{
  type: "cn_a_share_fee_execution_authority_v2",
  schema_version: 1,
  resolved_profile_digest,
  profile_composition_request_hash,
  market_profile_key,
  market_profile_version,
  market_profile_digest,
  execution_account_profile_key,
  execution_account_profile_version,
  execution_account_profile_digest,
  instrument_scope_declaration_hash,
  account_scope_declaration_hash,
  selection,
  selection_hash,
  access_route,
  fee_product_class,
  market_fee_rule_book,
  market_fee_rule_book_hash,
  stamp_duty_rule_book,
  stamp_duty_rule_book_hash,
  market_fee_component_ref,
  stamp_duty_component_ref
}
```

`authority_hash = canonical_sha256(body)`. Positive profile versions and every repeated selection/book/ref/hash field must exact-match its selection. Thus no market or stamp book can accompany the same authority interchangeably, even where monetary rates or route/product labels compare equal.

`cn_a_share_fee_v2.py` contains the only Runtime-specific helper, `_create_cn_a_share_fee_execution_authority_v2(resolved_profile, selection, /) -> CnAShareFeeExecutionAuthorityV2`. It is direct-module private and has no root export. It reads only the passed v1 `CnAShareResolvedProfile` and selection, binds the exact existing resolved-profile/request/digests/declaration hashes above, and accepts only the already frozen v1 facts: XSHE, CNY cash account, ordinary domestic A share, standard cash auction, no Stock Connect, no margin/short. It additionally requires `selection.access_route is DOMESTIC`, `selection.fee_product_class is ORDINARY_A_SHARE`, and XSHE-only selected books. This helper never selects a route/product, makes a default, or derives a class from metadata. Future Northbound/preferred/ETF profile paths are separate work.

### Exact Order binding and authoritative query constructors

`CnAShareFeeExecutionBindingV2` exact fields, in order:

1. `authority: CnAShareFeeExecutionAuthorityV2`
2. `authority_hash: str`
3. `order: Order`
4. `order_hash: str`
5. `order_id: DomainId`
6. `account_id: str`
7. `venue_id: VenueId`
8. `instrument_id: InstrumentId`
9. `side: OrderSide`
10. `order_effective_at: UtcInstant`

Its canonical type is `cn_a_share_fee_execution_binding_v2`; the body uses precisely the listed order and `binding_hash = canonical_sha256(body)`. It requires `authority_hash == authority.authority_hash`, `order_hash == canonical_sha256(order)`, `order_id == order.order_id`, account/Venue/Instrument/side equal the exact Order fields, `instrument_id.venue == venue_id`, `order_id.kind == ORDER`, and `order_effective_at == order.created_at.instant`.

The sole public binder is positional-only:

```python
bind_cn_a_share_fee_execution_v2(
    authority: CnAShareFeeExecutionAuthorityV2,
    order: Order,
    /,
) -> CnAShareFeeExecutionBindingV2
```

It derives every binding field from the exact values; it accepts neither route/product nor side/time inputs.

`CnAShareCashFeeRuleQueryV2` exact fields, in order:

1. `authority: CnAShareFeeExecutionAuthorityV2`
2. `authority_hash: str`
3. `execution_binding: CnAShareFeeExecutionBindingV2`
4. `binding_hash: str`
5. `purpose: CnAShareFeeAssessmentPurposeV2`
6. `fill: Fill | None`
7. `fill_hash: str | None`
8. `fill_id: DomainId | None`

Its canonical type is `cn_a_share_cash_fee_rule_query_v2`. Its canonical body contains those fields followed by the derived, non-constructor fields `order_id`, `order_hash`, `account_id`, `venue_id`, `instrument_id`, `side`, and `effective_at`, in that order. `query_hash = canonical_sha256(body)`.

The only constructors are positional-only class methods:

```python
CnAShareCashFeeRuleQueryV2.for_reservation(authority, execution_binding, /)
CnAShareCashFeeRuleQueryV2.for_final_fill(authority, execution_binding, fill, /)
```

`for_reservation` requires the same authority/hash as the binding, sets `purpose=RESERVATION`, all three Fill fields to `None`, and derives side/effective time from the bound Order (`order.intent.side`, `order.created_at.instant`). `for_final_fill` requires an exact `Fill`, sets `purpose=FINAL_FILL`, stores that Fill, `fill_hash=canonical_sha256(fill)`, and `fill_id=fill.fill_id`, and derives effective time only from `fill.execution_time`. Neither constructor accepts a caller side or effective time. Before RuleBook lookup, the policy validates that exact final Fill `order_id`, account, Venue, Instrument, and side against the binding and returns `FILL_BINDING_MISMATCH` atomically; it returns `EXECUTION_TIME_MISMATCH` when the Fill precedes `binding.order_effective_at`.

### Bands, RuleBooks, policies, components, and quantization

`CnAShareMarketFeeBandV2` exact fields are `venue_id: VenueId`, `effective_from: UtcInstant`, `effective_to_exclusive: UtcInstant`, `handling_applies: bool`, `handling_rate: Rate`, `handling_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]`, `regulatory_applies: bool`, `regulatory_rate: Rate`, `regulatory_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]`, `chinaclear_transfer_applies: bool`, `chinaclear_transfer_rate: Rate`, `chinaclear_transfer_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]`, `hkscc_transfer_applies: bool`, `hkscc_transfer_rate: Rate`, and `hkscc_transfer_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]`, in exactly that order. Its canonical type is `cn_a_share_market_fee_band_v2`; `band_hash` covers all fields. Intervals are finite, nonempty, half-open; rates are non-negative `fee_fraction`; false applies requires exact zero rate; every source-ref tuple is nonempty, canonical-sorted, and duplicate-free.

`CnAShareStampDutyBandV2` exact fields are `venue_id: VenueId`, `effective_from: UtcInstant`, `effective_to_exclusive: UtcInstant`, `applies_to_sell: bool`, `rate: Rate`, and `source_refs: tuple[CnAShareFeeRuleSourceRef, ...]`, in that order. Its canonical type is `cn_a_share_stamp_duty_band_v2`; the same interval/rate/source rules apply, and false sell applicability requires exact zero rate.

`CnAShareMarketFeeRuleBookV2` exact fields are `rule_book_key: str`, `rule_book_version: int`, `access_route: CnAShareExecutionAccessRoute`, `fee_product_class: CnAShareFeeProductClass`, and `bands: tuple[CnAShareMarketFeeBandV2, ...]`, in that order; its type is `cn_a_share_market_fee_rule_book_v2`. `CnAShareStampDutyRuleBookV2` exact fields are `rule_book_key: str`, `rule_book_version: int`, `access_route: CnAShareExecutionAccessRoute`, `fee_product_class: CnAShareFeeProductClass`, and `bands: tuple[CnAShareStampDutyBandV2, ...]`, in that order; its type is `cn_a_share_stamp_duty_rule_book_v2`. Both require `rule_book_version == 2`, derive `rule_book_hash = canonical_sha256(body)`, and sort Bands by Venue, half-open interval, then `band_hash`. They resolve only after authority/book route/product equality passes.

`CnAShareCashMarketFeePolicyV2` exact fields, in order, are `authority: CnAShareFeeExecutionAuthorityV2`, `authority_hash: str`, and `assessment_scale: Scale`; it exposes only `assess_fees(query: CnAShareCashFeeRuleQueryV2, /) -> ProfilePortOutcome[CnAShareMarketFeeRuleResolutionV2, CnAShareFeeRuleFailureV2]`. `CnAShareCashStampDutyTaxPolicyV2` exact fields, in order, are `authority: CnAShareFeeExecutionAuthorityV2`, `authority_hash: str`, and `assessment_scale: Scale`; it exposes only `assess_taxes(query: CnAShareCashFeeRuleQueryV2, /) -> ProfilePortOutcome[CnAShareStampDutyRuleResolutionV2, CnAShareFeeRuleFailureV2]`. Both require authority hash equality and `Scale(2)`, consume only the matching authority book/ref, and accept no RuleBook, side, time, or route/product argument.

The component preimages are exact:

```text
market = {
  type: "cn_a_share_cash_market_fee_component_v2", schema_version: 1,
  component_key: "equity.cn_a_share.cash.market-fees.route-product.v2",
  component_version: 2,
  algorithm_key: "cn-a-share-historical-market-fees-route-product-v2",
  rule_book_hash, access_route, fee_product_class,
  assessment_scale: 2, rounding: "half_up",
  quantization_version: "cn-a-share-market-fee.cny-cent.half-up.v2"
}
tax = {
  type: "cn_a_share_cash_stamp_duty_component_v2", schema_version: 1,
  component_key: "equity.cn_a_share.cash.stamp-duty.route-product.v2",
  component_version: 2,
  algorithm_key: "cn-a-share-historical-stamp-duty-route-product-v2",
  rule_book_hash, access_route, fee_product_class,
  assessment_scale: 2, rounding: "half_up",
  quantization_version: "cn-a-share-stamp-duty.cny-cent.half-up.v2"
}
```

`ProfileComponentRef.digest` is `canonical_sha256` of the respective body. Market generated charge order is exactly:

```text
exchange_handling
securities_regulatory
chinaclear_transfer
hkscc_transfer
```

False applicability emits `NOT_APPLICABLE`, never an applied zero charge. ChinaClear and HKSCC never share a key, source tuple, or ID preimage.

For each generated market/tax rule, the exact ID preimage is:

```text
{
  type: "cn_a_share_fee_generated_rule_id_v2", schema_version: 1,
  component_key, component_version, component_digest, rule_book_hash, band_hash,
  authority_hash, binding_hash, query_hash, access_route, fee_product_class,
  charge_key, purpose, basis_type, applies, source_refs, quantization_version
}
```

`purpose` is `reservation`, `final_fill`, or `final_order`; `basis_type` is respectively `order_notional`, `fill`, or `order`; `quantization_version` is the fixed market or tax version above. A rule’s tag is respectively `cn-a-share-market-fee-rule-v2` or `cn-a-share-stamp-duty-rule-v2`, followed by `:` and `canonical_sha256(preimage)`.

### Results, failures, and buffer

`CnAShareMarketFeeRuleResolutionV2` exact fields, in order, are `authority: CnAShareFeeExecutionAuthorityV2`, `authority_hash: str`, `query: CnAShareCashFeeRuleQueryV2`, `query_hash: str`, `binding_hash: str`, `order_id: DomainId`, `order_hash: str`, `fill: Fill | None`, `fill_hash: str | None`, `fill_id: DomainId | None`, `side: OrderSide`, `effective_at: UtcInstant`, `active_band: CnAShareMarketFeeBandV2`, `active_band_hash: str`, `reservation_charge_rules: tuple[FeeReservationChargeRule, ...]`, `final_fill_charge_rules: tuple[FinalFeeChargeRule, ...]`, and `final_order_not_applicable_rule: FinalFeeChargeRule`. Its canonical type is `cn_a_share_market_fee_rule_resolution_v2`; `resolution_hash` covers every field. Reservation has `fill/fill_hash/fill_id=None` and exactly four reservation rules; final Fill has the exact Fill/hash/ID and exactly four final rules; both have exactly one final-order coverage rule. All derived identity/time fields reconstruct from the query.

`CnAShareStampDutyRuleResolutionV2` exact fields, in order, are `authority: CnAShareFeeExecutionAuthorityV2`, `authority_hash: str`, `query: CnAShareCashFeeRuleQueryV2`, `query_hash: str`, `binding_hash: str`, `order_id: DomainId`, `order_hash: str`, `fill: Fill | None`, `fill_hash: str | None`, `fill_id: DomainId | None`, `side: OrderSide`, `effective_at: UtcInstant`, `active_band: CnAShareStampDutyBandV2`, `active_band_hash: str`, `reservation_charge_rule: FeeReservationChargeRule`, `final_fill_charge_rule: FinalFeeChargeRule`, and `final_order_not_applicable_rule: FinalFeeChargeRule`. Its canonical type is `cn_a_share_stamp_duty_rule_resolution_v2`; `resolution_hash` covers every field and all identity/time fields reconstruct from the query.

`CnAShareFeeRuleFailureCodeV2` declaration and first-applicable order are exactly:

1. `UNSUPPORTED_VENUE = "unsupported_venue"`
2. `UNSUPPORTED_INSTRUMENT = "unsupported_instrument"`
3. `UNSUPPORTED_CURRENCY = "unsupported_currency"`
4. `UNSUPPORTED_TRADE_MECHANISM = "unsupported_trade_mechanism"`
5. `EXECUTION_AUTHORITY_MISMATCH = "execution_authority_mismatch"`
6. `EXECUTION_BINDING_MISMATCH = "execution_binding_mismatch"`
7. `ORDER_SIDE_MISMATCH = "order_side_mismatch"`
8. `FILL_BINDING_MISMATCH = "fill_binding_mismatch"`
9. `EXECUTION_TIME_MISMATCH = "execution_time_mismatch"`
10. `ROUTE_PRODUCT_MISMATCH = "route_product_mismatch"`
11. `MISSING_RULE_INTERVAL = "missing_rule_interval"`
12. `OVERLAPPING_RULE_INTERVALS = "overlapping_rule_intervals"`

Authority mismatch checks authority/hash/ref/book identity; binding mismatch checks authority/order hash/ID/account/Venue/Instrument; side mismatch checks bound Order side; final-only Fill mismatch checks Fill Order/account/Venue/Instrument/side; final-only execution-time mismatch checks `fill.execution_time < binding.order_effective_at`; route/product mismatch precedes interval lookup. Constructor-forged self-identities are rejected before policy evaluation. This order is the required multi-defect precedence.

`CnAShareFeeRuleFailureV2` exact fields are `query: CnAShareCashFeeRuleQueryV2`, `query_hash: str`, `code: CnAShareFeeRuleFailureCodeV2`, and `subject_ids: tuple[str, ...]`, in that order. Its type is `cn_a_share_fee_rule_failure_v2`; `failure_hash` is derived. `subject_ids` is exactly `(code.value, query_hash, binding_hash, *canonical_unique_subject_ids)` and no partial rules accompany failure.

`CnAShareFeeReservationBufferV2` exact fields are `market_resolution: CnAShareMarketFeeRuleResolutionV2`, `tax_resolution: CnAShareStampDutyRuleResolutionV2`, `maximum_fill_count: int`, `market_charge_rule: FeeReservationChargeRule`, and `tax_charge_rule: FeeReservationChargeRule`, in that order. Its type is `cn_a_share_fee_reservation_buffer_v2`; `buffer_hash` is derived. It accepts reservation resolutions only, exact-matching authority/binding/query/order/side/effective time, and a positive count. With `u=floor(maximum_fill_count/2)` CNY cents, market is `m*u`, tax is `t*u`; domestic ordinary has `m=3`, a separately evidenced Northbound ordinary book with HKSCC has `m=4`, and `t=1` only for SELL.

The market/tax buffer IDs use tags `cn-a-share-market-fee-rounding-buffer-v2` and `cn-a-share-tax-rounding-buffer-v2`. Their exact preimage is:

```text
{
  type: "cn_a_share_fee_reservation_buffer_rule_id_v2", schema_version: 1,
  component_key, component_version, component_digest, authority_hash, binding_hash,
  market_resolution_hash, tax_resolution_hash, maximum_fill_count, component_count,
  side, applicability, basis_type: "flat_per_order", amount, currency: "CNY",
  amount_scale: 2, quantization_version: "cn-a-share-fee-reservation-buffer.cny-cent.half-up.v2"
}
```

Actual Fill count above the positive bound fails closed. Account commission/minimum never enters this type.

## Finite v1-to-v2 compatibility projection

The only projection is positional-only:

```python
project_cn_a_share_domestic_ordinary_fee_rules_v2(
    market_rule_book: CnAShareMarketFeeRuleBook,
    stamp_duty_rule_book: CnAShareStampDutyRuleBook,
    /,
) -> CnAShareDomesticOrdinaryFeeProjectionV2
```

It rejects before any output construction unless every source Band in both books has `venue_id == VenueId("xshe")`; it never filters or drops XSHG silently. It preserves each finite interval without extension, coalescing, or reinterpretation: v1 handling → handling applies; v1 regulatory → regulatory applies; v1 transfer → ChinaClear applies; v1 stamp duty → sell applicability. HKSCC is false/zero but has exactly one deterministic nonempty `CnAShareFeeRuleSourceRef` with key `cn-a-share-domestic-ordinary-v1-to-v2-hkscc-not-applicable` and hash `canonical_sha256({type: "cn_a_share_fee_compatibility_hkscc_source_v2", schema_version: 1, source_market_rule_book_hash, source_stamp_duty_rule_book_hash, venue_id: "xshe", effective_from, effective_to_exclusive, access_route: "domestic", fee_product_class: "ordinary_a_share", charge_key: "hkscc_transfer", applies: false})`.

Output keys are `equity.cn_a_share.cash.market-fees.domestic.ordinary-a-share.projected-v2` and `equity.cn_a_share.cash.stamp-duty.domestic.ordinary-a-share.projected-v2`; both are version 2, XSHE-only, and `DOMESTIC + ORDINARY_A_SHARE` only.

`CnAShareDomesticOrdinaryFeeProjectionV2` exact fields are `algorithm_id: str`, `source_market_rule_book: CnAShareMarketFeeRuleBook`, `source_market_rule_book_hash: str`, `source_stamp_duty_rule_book: CnAShareStampDutyRuleBook`, `source_stamp_duty_rule_book_hash: str`, `access_route: CnAShareExecutionAccessRoute`, `fee_product_class: CnAShareFeeProductClass`, `market_fee_rule_book: CnAShareMarketFeeRuleBookV2`, `market_fee_rule_book_hash: str`, `stamp_duty_rule_book: CnAShareStampDutyRuleBookV2`, and `stamp_duty_rule_book_hash: str`, in that order. Its type is `cn_a_share_domestic_ordinary_fee_projection_v2`; `algorithm_id` is exactly `cn-a-share-domestic-ordinary-v1-to-v2-fee-projection-v1`; `projection_hash` is derived. It is a finite compatibility proof only, not official evidence, open-ended continuity, July-2026 coverage, provider qualification, or a Northbound/preferred/ETF book.


## Architecture and public rules

- Reuse existing generic `FeeAssessmentPolicy`, `TaxPolicy`, `ProfilePortOutcome`, `FeeReservationEstimator`, `FeeAssessmentEngine`, RuleSet, Journal, and Ledger contracts unchanged.
- No new Protocol, generic port, interface, registry, resolver, factory framework, DSL, callback, plugin, cache, provider adapter, Runtime market branch, or second fee engine.
- Kernel concrete-profile code may import v1 sibling types only for the pure projection. Generic Kernel modules never import concrete A-share code.
- Runtime profile-authority binding is private, profile-specific, and isolated; Engine, Runner, composition, financial dispatch, and resolution remain free of A-share branches.
- Builder imports neither Kernel nor Runtime. This slice adds no Builder code.
- V2 Kernel names are concrete-submodule public; existing `cn_a_share.__all__` v1 members/order remain exact and only the declared v2 names append. The private Runtime helper and both package roots remain unchanged. Existing G08H root import set remains exact.
- Production never imports `tests.support`; test support never becomes semantic authority.

## Staged delivery

### F0 — contract freeze — this change

Accept ADR 0005, freeze this plan, add glossary terms, and update G12H status/sequence. No implementation artifacts.

### F1 — contract RED

Add only the additive tests and expected fixture bodies listed above. RED must fail because the v2 symbols/modules do not exist, while all v1 tests and protected-byte assertions pass. Do not modify production code in the RED commit.

### F2 — Kernel GREEN

Implement only `commission_tax_v2.py` and concrete submodule exports: exact selection, authority, Order binding, authoritative reservation/final query constructors, policies, results/failures/buffer, and XSHE-only compatibility projection. Make kernel RED/golden tests pass. Rerun all G08E v1 tests and byte locks.

### F3 — private profile-authority binding GREEN

Implement only `cn_a_share_fee_v2.py` and the additive test-support module. Make the private authority helper validate an explicit selection against the frozen v1 profile and make binding tests pass without modifying the v1 composer, registry, root exports, existing journey, or fixture bytes.

### F4 — contract acceptance

Run focused/full validation, architecture/import checks, protected-byte locks, canonical mutation tests, mypy, lock/diff/gitleaks/status checks, and independent review. Only then set this contract `PASSED` in a separate authorized status change.

### F5 — G12H F1 resume

After F4 passes, G12H may resume source acquisition for `DOMESTIC + ORDINARY_A_SHARE` only. G12H remains responsible for July-2026 successor closure, target projection, publication, and coverage analysis. It must use separately keyed effective-until-superseded v2 books, not the finite compatibility projection.

## RED matrix

### Public shape and no-default controls

- enum member names, values, and order are exact;
- every field/signature above is exact and has no default;
- v1 signatures, field lists, root imports, and every existing `cn_a_share.__all__` member/order remain exact; only declared v2 names append;
- new canonical types use their own type literals and cannot serialize as v1.

### Binding and scope controls

- an explicit selection plus the successful frozen G08H profile yields one stable authority/hash; altering any resolved-profile/request/declaration identity, component ref/digest, book body/hash, route, or product changes it;
- the private Runtime helper rejects any non-domestic/non-ordinary/Stock-Connect/ineligible-v1 profile selection and never manufactures route/product;
- an authority cannot pair either of its books with another authority, including equal-rate/equal-scope books;
- exact Order binding changes on canonical Order/hash, Order ID, Account, Venue, Instrument, side, or order-created instant mutation;
- reservation construction accepts no side/time and uses bound Order side/created instant; final construction accepts no side/time and uses exact Fill side/execution time;
- final Fill order/account/Venue/Instrument/side mismatch returns `FILL_BINDING_MISMATCH`; pre-order Fill execution time returns `EXECUTION_TIME_MISMATCH` after `ORDER_SIDE_MISMATCH` and before route/product/interval checks;
- domestic authority against Northbound book, ordinary authority against preferred/ETF book, or market/tax books with different scope returns `ROUTE_PRODUCT_MISMATCH` before interval lookup;
- symbol/stable-key mutations do not infer route/product; omitted route/product is a construction error, never domestic/ordinary default.

### Economic and component controls

- XSHE-only finite v1 projection preserves exact interval/rate/source economics for handling, regulatory, ChinaClear, and stamp duty; any XSHG source Band rejects before output construction;
- every v2 source-ref tuple is nonempty; compatibility HKSCC not-applicability has its deterministic interval/source-book-derived ref;
- projection creates new selection/authority/query/book/component/rule/resolution hashes even when monetary outputs match v1;
- domestic ordinary result has four market rules with HKSCC explicitly not applicable;
- Northbound ordinary control requires a separate book and can carry ChinaClear plus HKSCC simultaneously;
- ChinaClear and HKSCC source/rule IDs remain distinct under equal rates, zero rates, reorder attempts, and source mutation;
- preferred and ETF books do not resolve through ordinary books;
- ETF waiver controls are not-applicable rules, not applied zero charges;
- every Fill resolves by its execution time; no acceptance-time or first-Fill reuse;
- gap/overlap remains finite and fail closed.

### Precedence and atomicity controls

- each policy failure code has a direct malformed authority/binding/query control, while reconstructable self-forgery is constructor-rejected;
- multi-defect inputs return the exact first failure order;
- authority mismatch precedes binding mismatch; binding mismatch precedes order-side/final-Fill/time mismatch; time mismatch precedes route/product mismatch; route/product mismatch precedes gap/overlap;
- failures return no partial reservation/final rules or projection.

### Reservation/final controls

- domestic ordinary `maximum_fill_count=2` keeps the v1 three-market-component buffer amount but has a new v2 authority/binding/query/buffer/rule identity;
- a separately evidenced Northbound ordinary control uses four market components;
- BUY stamp duty remains not applicable; SELL behavior follows the v2 tax Band;
- final resolution canonically binds exact Fill, Fill hash, Fill ID, derived side, and `Fill.execution_time`;
- Fill-count overflow fails closed; generic estimator/assessment/Journal outputs require no A-share branch.

### Canonical and forgery controls

- canonical input reorder normalizes where declared; semantic order remains fixed where declared;
- forged selection/authority/binding/query/fill hash, Band hash, RuleBook hash, component ref/digest, resolution rules/order/Fill context, projection source/output hash, and buffer hash are rejected;
- mutation of route/product/applies/source/rate/interval/profile/request/order/Fill/component context propagates through all v2 identities;
- v1 canonical bytes and hashes remain unchanged under all v2 imports and tests.

### Architecture/nonclaim controls

- only the two allowed production modules appear;
- no Runtime root export, generic root export, registry, Builder, provider, network, filesystem, process, database, wall clock, dynamic import, or test-support production import appears;
- non-notional portfolio/instruction/settlement costs are absent from query, Band, RuleBook, generated rule, and fixture schemas;
- all qualification/deployment flags remain false or absent; no provider or July-2026 claim appears.

## Validation commands for implementation phases

```bash
uv run pytest -q \
  tests/kernel/profiles/cn_a_share/test_commission_tax_v2_contract.py \
  tests/kernel/profiles/cn_a_share/test_commission_tax_v2_golden.py \
  tests/runtime/profiles/cn_a_share/test_fee_execution_binding_v2.py \
  tests/architecture/test_g08e_route_product_fee_v2_boundary.py

uv run pytest -q \
  tests/kernel/profiles/cn_a_share/test_commission_tax.py \
  tests/kernel/profiles/cn_a_share/test_commission_tax_golden.py \
  tests/runtime/profiles/cn_a_share \
  tests/support/cn_a_share \
  tests/architecture/test_g08h_cn_a_share_composition_boundary.py

sha256sum \
  tests/fixtures/kernel/profiles/cn_a_share/commission-tax-v1.json \
  tests/fixtures/runtime/profiles/cn-a-share-resolved-profile-composition-v1.json \
  tests/fixtures/runtime/engine/cn-a-share-resolved-profile-development-journey-v1.json \
  tests/fixtures/market_data/rule_authorities/cn-a-share-development-v1/declaration.json \
  tests/fixtures/market_data/rule_authorities/cn-a-share-development-v1/publication.expected.json

uv run python tools/architecture/check_import_boundaries.py \
  --root . --policy architecture/import-boundaries.toml \
  --report build/acceptance/g08e-route-product-v2-import-boundary-report.json

uv run mypy packages/trading-kernel/src packages/backtest-runtime/src
uv run pytest -q
uv lock --check
git diff --check
gitleaks detect --source . --no-banner --redact --log-opts="--all"
git status --short
```

Link/semantic assertions additionally check every referenced path, ADR status, plan status, exact enum literals, exact charge order, explicit F1 dependency on contract `PASSED`, no contradictory full-envelope language in G12H, and no edits to prohibited files.

## G12H unblocking sequence

1. This plan remains `READY_FOR_CONTRACT_RED`; G12H F1 remains blocked.
2. Contract RED freezes exact failure/canonical/byte behavior.
3. Kernel and Runtime binding GREEN pass independently.
4. Contract acceptance proves exact authority/book non-interchangeability, private profile binding, Order/Fill constructor precedence, protected bytes, architecture, and semantics; only then may status become `PASSED`.
5. G12H F1 acquires and closes official evidence only for `DOMESTIC + ORDINARY_A_SHARE` and the five explicit lineages, including HKSCC as route-not-applicable evidence. F1 is not an authority/policy prerequisite and creates no circular acceptance dependency.
6. G12H F2 creates separately keyed July-2026 effective-until-superseded v2 RuleBooks; it does not use the finite compatibility projection as authority.
7. G12H F3 publishes a new additive declaration/Bundle identity.
8. Only after F1-F3 pass may G12H analyzer RED resume; only analyzer GREEN may close the existing `COVERAGE_GAP / market_fees` result.

## Nonclaims and prohibited scope

This contract does not claim complete July-2026 evidence, provider/archive completeness, broker commission/minimum, bundled fees, rebates, VAT, official rounding parity, block/after-hours trading, B shares, funds, bonds, margin/short, non-CNY trading, account-statement parity, broader Stock Connect qualification, preferred-stock qualification, ETF qualification, live/current use, decision grade, or deployment authorization.

It does not model daily portfolio-value fees, CPI/SI/STI or other instruction fees, money settlement, safekeeping, collateral, corporate-action service, or other participant/state/message-based costs. Add those only after a separate basis/state contract is accepted.

Do not modify code, fixtures, registry, Acceptance Matrix, plan README, or publication artifacts in this docs freeze. Do not merge or push as part of the plan freeze.
