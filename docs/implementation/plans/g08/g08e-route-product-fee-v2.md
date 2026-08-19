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

The implementation contract is not `PASSED`. G12H F1 remains blocked until the complete Authority/Profile Binding Proof, exact three-argument private profile/build semantic-binding seam, Order/Fill constructors, canonical query-provenance check, and both v2 policies pass compatibility, semantic, architecture, and byte-lock acceptance. That acceptance is independent of G12H: it uses only the finite XSHE v1-to-v2 compatibility projection.

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

Do not modify `commission_tax.py`, `cn_a_share_profile.py`, generic fee/tax ports, generic fee arithmetic, Engine, Runner, Dispatcher, Journal, Ledger, v1 profile registry entries, Runtime root exports, Builder, or market-data packages. One additive profile-specific v2 build registration in `cn_a_share_fee_v2.py` is allowed only to bind the v2 authority/proof into a new unique profile/build identity before execution; it does not mutate or reinterpret any v1 registration.

`commission_tax_v2.py` may import stdlib, `crypto_quant_domain`, existing generic fee/reservation/port contracts, and the v1 A-share fee types needed by the compatibility projection. It performs no I/O and imports no Runtime, Builder, provider, repository, filesystem, network, database, process, wall clock, dynamic loader, or test code.

`cn_a_share_fee_v2.py` is the private pure profile-authority and v2 profile-build binding seam. It may import v1 `CnAShareResolvedProfile` and only these v2 Kernel types: `CnAShareFeeExecutionScopeV2`, `CnAShareFeeExecutionSelectionV2`, `CnAShareFeeProfileBindingProofV2`, `CnAShareFeeExecutionAuthorityV2`, `CnAShareFeeExecutionAuthorityBuildFailureCodeV2`, `CnAShareFeeExecutionAuthorityBuildFailureV2`, and `CnAShareFeeExecutionSemanticBindingV2` (the build outcome/binding types). It contains exactly `_create_cn_a_share_fee_execution_authority_v2(resolved_profile, scope, selection, /) -> CnAShareFeeExecutionAuthorityV2 | CnAShareFeeExecutionAuthorityBuildFailureV2`; no two-argument form exists. It imports no Engine, Runner, Builder, provider, repository, filesystem, network, database, process, wall clock, callback, or implementation object identity. It is not imported or exported by `crypto_quant_backtest.__init__`.

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
CnAShareFeeExecutionScopeV2
CnAShareFeeExecutionSelectionV2
CnAShareFeeProfileBindingProofV2
CnAShareFeeExecutionAuthorityV2
CnAShareFeeExecutionSemanticBindingV2
CnAShareFeeExecutionAuthorityBuildFailureCodeV2
CnAShareFeeExecutionAuthorityBuildFailureV2
CnAShareFeeExecutionBindingV2
CnAShareFeeExecutionBindingFailureCodeV2
CnAShareFeeExecutionBindingFailureV2
CnAShareCashFeeRuleQueryV2
CnAShareFeeQueryConstructionFailureCodeV2
CnAShareFeeQueryConstructionFailureV2
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

### Scope, selection, and profile-bound fee authority

`CnAShareFeeExecutionScopeV2` is the explicit immutable execution scope. Its exact fields, in order, are:

1. `account_id: str`
2. `venue_id: VenueId`
3. `instrument: InstrumentDefinition`
4. `instrument_id: InstrumentId`
5. `instrument_type: InstrumentType`
6. `quote_currency_id: CurrencyId`
7. `settlement_currency_id: CurrencyId`
8. `trade_mechanism: CnAShareFeeTradeMechanism`
9. `coverage_from: UtcInstant`
10. `coverage_to_exclusive: UtcInstant`
11. `allowed_order_sides: tuple[OrderSide, ...]`
12. `access_route: CnAShareExecutionAccessRoute`
13. `fee_product_class: CnAShareFeeProductClass`
14. `is_ordinary_domestic_a_share: bool`
15. `is_standard_cash_auction: bool`
16. `is_stock_connect: bool`
17. `is_cash_account: bool`
18. `is_domestic_access: bool`
19. `has_margin_or_short_permission: bool`
20. `has_stock_connect_permission: bool`

Its canonical type is `cn_a_share_fee_execution_scope_v2`; its body uses that exact field order; `scope_hash = canonical_sha256(body)`. Constructor validation is structural only: exact value types, canonical text, `instrument.instrument_id == instrument_id`, `instrument.instrument_type == instrument_type`, `instrument_id.venue == venue_id`, finite half-open `coverage_from/coverage_to_exclusive`, canonical unique `allowed_order_sides` sorted by enum declaration order, and exact `bool` fields. It does not determine whether the scope is supported.

`CnAShareFeeExecutionSelectionV2` is the explicit immutable build selection. Its exact fields, in order, are `selection_key: str`, `selection_version: int`, `access_route: CnAShareExecutionAccessRoute`, `fee_product_class: CnAShareFeeProductClass`, `market_fee_rule_book: CnAShareMarketFeeRuleBookV2`, `market_fee_rule_book_hash: str`, `stamp_duty_rule_book: CnAShareStampDutyRuleBookV2`, `stamp_duty_rule_book_hash: str`, `market_fee_component_ref: ProfileComponentRef`, and `stamp_duty_component_ref: ProfileComponentRef`. Its canonical type is `cn_a_share_fee_execution_selection_v2`; its body uses that exact order; `selection_hash = canonical_sha256(body)`. Constructor validation is structural only: positive version, canonical primitive/hash form, and exact concrete member types. It does not choose a route/product or pair books by inference.

`CnAShareFeeProfileBindingProofV2` is the canonical proof produced by the private Runtime authority builder for accepted v2 execution; direct construction is structurally possible but cannot satisfy execution selection without the matching semantic binding below. Its exact fields, in order, are:

1. `resolved_profile_key: str`
2. `resolved_profile_version: int`
3. `resolved_profile_digest: str`
4. `composition_request_type: str`
5. `composition_request_schema_version: int`
6. `composition_request_hash: str`
7. `composition_request_body_hash: str`
8. `market_component_manifest_hash: str`
9. `source_manifest_hash: str`
10. `instrument_scope_declaration_hash: str`
11. `account_scope_declaration_hash: str`
12. `account_id: str`
13. `venue_id: VenueId`
14. `instrument_id: InstrumentId`
15. `scope_hash: str`
16. `selection_hash: str`
17. `market_fee_rule_book_hash: str`
18. `stamp_duty_rule_book_hash: str`
19. `market_fee_component_ref: ProfileComponentRef`
20. `stamp_duty_component_ref: ProfileComponentRef`

Its canonical type is `cn_a_share_fee_profile_binding_proof_v2`; its canonical body uses precisely that order; `profile_binding_hash = canonical_sha256(body)`. `composition_request_type` is exactly `cn_a_share_profile_composition_request`, `composition_request_schema_version` is exactly `1`, and the builder reconstructs the exact v1 resolved-profile key/version/digest, request body/hash, market-component manifest hash, source-manifest hash, instrument/account declaration hashes, Scope/selection hashes, book hashes, and component refs/digests. A proof is canonical evidence of that reconstruction, not a cryptographic claim about how a caller obtained its input.

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
11. `profile_binding_proof: CnAShareFeeProfileBindingProofV2`
12. `profile_binding_hash: str`
13. `scope: CnAShareFeeExecutionScopeV2`
14. `scope_hash: str`
15. `selection: CnAShareFeeExecutionSelectionV2`
16. `selection_hash: str`
17. `access_route: CnAShareExecutionAccessRoute`
18. `fee_product_class: CnAShareFeeProductClass`
19. `market_fee_rule_book: CnAShareMarketFeeRuleBookV2`
20. `market_fee_rule_book_hash: str`
21. `stamp_duty_rule_book: CnAShareStampDutyRuleBookV2`
22. `stamp_duty_rule_book_hash: str`
23. `market_fee_component_ref: ProfileComponentRef`
24. `stamp_duty_component_ref: ProfileComponentRef`

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
  profile_binding_proof,
  profile_binding_hash,
  scope,
  scope_hash,
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

`authority_hash = canonical_sha256(body)`. Its constructor only enforces exact primitives, canonical hashes, positive profile versions, and concrete types. The private builder reconstructs every proof field and then requires proof/hash equality to the Authority's profile/request/declaration/Scope/selection/book/component fields. Semantic equality between repeated fields is owned by the private builder or policy, never hidden in a constructor.

#### Authority-builder ownership

`cn_a_share_fee_v2.py` contains the only Runtime-specific helper:

```python
_create_cn_a_share_fee_execution_authority_v2(
    resolved_profile: CnAShareResolvedProfile,
    scope: CnAShareFeeExecutionScopeV2,
    selection: CnAShareFeeExecutionSelectionV2,
    /,
) -> CnAShareFeeExecutionAuthorityV2 | CnAShareFeeExecutionAuthorityBuildFailureV2
```

It is direct-module private, reads only passed values, has no registry lookup, and is not a root export. It exact-binds the existing resolved Profile/request/digests/declaration identities, Scope/body hash, selection/body hash, books, and refs. It is the sole owner of whether the v1 profile supports the Scope and selection.

`CnAShareFeeExecutionAuthorityBuildFailureCodeV2` exact first-applicable order is:

1. `PROFILE_SCOPE_MISMATCH = "profile_scope_mismatch"`
2. `UNSUPPORTED_VENUE = "unsupported_venue"`
3. `UNSUPPORTED_INSTRUMENT = "unsupported_instrument"`
4. `UNSUPPORTED_CURRENCY = "unsupported_currency"`
5. `UNSUPPORTED_TRADE_MECHANISM = "unsupported_trade_mechanism"`
6. `ROUTE_PRODUCT_SCOPE_MISMATCH = "route_product_scope_mismatch"`
7. `RULE_BOOK_SCOPE_MISMATCH = "rule_book_scope_mismatch"`
8. `COMPONENT_REF_MISMATCH = "component_ref_mismatch"`

`PROFILE_SCOPE_MISMATCH` compares every Scope profile-fact and declaration-backed Account/Instrument context to the passed v1 resolved Profile. The next four test XSHE, broad Equity, CNY quote/settlement, and Auction. `ROUTE_PRODUCT_SCOPE_MISMATCH` requires Scope and Selection to agree and the frozen v1 path to be exactly DOMESTIC + ORDINARY_A_SHARE; `RULE_BOOK_SCOPE_MISMATCH` requires both selected books/hashes to match selection and exact Scope route/product/XSHE; `COMPONENT_REF_MISMATCH` reconstructs both exact component refs/digests. The helper never manufactures defaults. Future Northbound/preferred/ETF builders are separate work.

`CnAShareFeeExecutionAuthorityBuildFailureV2` exact fields are `resolved_profile_digest: str`, `profile_composition_request_hash: str`, `scope: CnAShareFeeExecutionScopeV2`, `scope_hash: str`, `selection: CnAShareFeeExecutionSelectionV2`, `selection_hash: str`, `code: CnAShareFeeExecutionAuthorityBuildFailureCodeV2`, and `subject_ids: tuple[str, ...]`, in that order. Its type is `cn_a_share_fee_execution_authority_build_failure_v2`; `failure_hash` is derived. Its fixed subject prefix is exactly `(code.value, resolved_profile_digest, profile_composition_request_hash, scope_hash, selection_hash)`, followed only by the code-specific suffix below; no subject tuple is deduplicated or sorted.

| code | exact suffix in order |
| --- | --- |
| `PROFILE_SCOPE_MISMATCH` | `("instrument_scope_declaration_hash", resolved_profile.request.instrument_scope.declaration_hash, "account_scope_declaration_hash", resolved_profile.request.account_scope.declaration_hash)` |
| `UNSUPPORTED_VENUE` | `("venue_id", scope.venue_id.value)` |
| `UNSUPPORTED_INSTRUMENT` | `("instrument_id", str(scope.instrument_id), "instrument_type", scope.instrument_type.value)` |
| `UNSUPPORTED_CURRENCY` | `("quote_currency_id", str(scope.quote_currency_id), "settlement_currency_id", str(scope.settlement_currency_id))` |
| `UNSUPPORTED_TRADE_MECHANISM` | `("trade_mechanism", scope.trade_mechanism.value)` |
| `ROUTE_PRODUCT_SCOPE_MISMATCH` | `("scope_access_route", scope.access_route.value, "selection_access_route", selection.access_route.value, "scope_fee_product_class", scope.fee_product_class.value, "selection_fee_product_class", selection.fee_product_class.value)` |
| `RULE_BOOK_SCOPE_MISMATCH` | `("market_fee_rule_book_hash", selection.market_fee_rule_book_hash, "stamp_duty_rule_book_hash", selection.stamp_duty_rule_book_hash, "scope_venue_id", scope.venue_id.value)` |
| `COMPONENT_REF_MISMATCH` | `("market_fee_component_digest", selection.market_fee_component_ref.component_digest, "stamp_duty_component_digest", selection.stamp_duty_component_ref.component_digest)` |

All labels above are literal strings; Domain IDs use `.value`, venue/type/enum values use `.value`, and hashes are their canonical `sha256:` text. Therefore `failure_hash = canonical_sha256(failure body)` is unique and reproducible.

### V2 profile/build semantic binding

`CnAShareFeeExecutionSemanticBindingV2` is the execution-selected expected authority context consumed by both policies. Its exact fields, in order, are:

1. `profile_binding_proof: CnAShareFeeProfileBindingProofV2`
2. `profile_binding_hash: str`
3. `authority: CnAShareFeeExecutionAuthorityV2`
4. `authority_hash: str`
5. `profile_build_key: str`
6. `profile_build_version: int`
7. `profile_build_manifest_hash: str`
8. `financial_semantic_identity_hash: str`
9. `semantic_run_input_hash: str`

Its canonical type is `cn_a_share_fee_execution_semantic_binding_v2`; its canonical body uses precisely that order; `semantic_binding_hash = canonical_sha256(body)`. It requires `profile_build_key == "equity.cn_a_share.fee-execution.v2"` and `profile_build_version == 2`. Constructor validation is only exact primitive/concrete type and canonical hash form; private F3 construction owns full reconstruction.

The same private Runtime module contains `_bind_cn_a_share_fee_execution_profile_build_v2(resolved_profile, authority, /) -> CnAShareFeeExecutionSemanticBindingV2`. It reconstructs the proof from `resolved_profile`, requires exact proof/hash and Authority equality, then creates a **new additive** profile/build registration with key/version above. It does not claim to prove the historical origin of a structurally valid Authority; policy acceptance requires this execution-selected binding. It neither mutates the immutable v1 `CnAShareResolvedProfile`, v1 registrations, v1 component manifest, nor root exports.

The v2 profile/build manifest preimage is exactly:

```text
{
  type: "cn_a_share_fee_execution_profile_build_manifest_v2",
  schema_version: 1,
  profile_build_key: "equity.cn_a_share.fee-execution.v2",
  profile_build_version: 2,
  base_resolved_profile_digest,
  base_composition_request_hash,
  base_market_component_manifest_hash,
  base_source_manifest_hash,
  profile_binding_hash,
  authority_hash,
  market_fee_component_ref,
  stamp_duty_component_ref
}
```

`profile_build_manifest_hash = canonical_sha256(body)`. The financial semantic preimage is exactly:

```text
{
  type: "cn_a_share_fee_execution_financial_semantic_identity_v2",
  schema_version: 1,
  profile_build_manifest_hash,
  base_financial_dispatcher_spec_hash,
  profile_binding_hash,
  authority_hash,
  market_fee_component_ref,
  stamp_duty_component_ref
}
```

`financial_semantic_identity_hash = canonical_sha256(body)`. `semantic_run_input_hash = canonical_sha256({type: "cn_a_share_fee_execution_semantic_run_input_v2", schema_version: 1, profile_build_manifest_hash, financial_semantic_identity_hash, profile_binding_hash, authority_hash})`. F3 registers this additive binding before execution, hash-binds the immutable existing v1 profile/build manifest as `base_*` fields above, and inserts `profile_build_manifest_hash`, `financial_semantic_identity_hash`, `profile_binding_hash`, `authority_hash`, and `semantic_run_input_hash` into the v2-only profile/build manifest and `ExecutionCaseSemanticSpec`/Semantic Run input preimage. The v1 semantic spec and bytes remain unchanged. Therefore substituting a structurally valid different Authority changes the v2 request/Semantic Run identity; a request carrying hashes inconsistent with its selected semantic binding is rejected before execution. This is canonical builder-equivalence plus runtime semantic binding, not a cryptographic provenance claim.

### Exact Order binding and query-construction ownership

`CnAShareFeeExecutionBindingV2` exact fields, in order, are `authority: CnAShareFeeExecutionAuthorityV2`, `authority_hash: str`, `order: Order`, `order_hash: str`, `order_id: DomainId`, `account_id: str`, `venue_id: VenueId`, `instrument_id: InstrumentId`, `side: OrderSide`, and `order_effective_at: UtcInstant`. Its canonical type is `cn_a_share_fee_execution_binding_v2`; the body uses precisely that order; `binding_hash = canonical_sha256(body)`. Its constructor enforces only exact primitive/concrete type and canonical hash form, including `order_id.kind == ORDER` and `instrument_id.venue == venue_id`.

The sole public binder is positional-only:

```python
bind_cn_a_share_fee_execution_v2(
    authority: CnAShareFeeExecutionAuthorityV2,
    order: Order,
    /,
) -> CnAShareFeeExecutionBindingV2 | CnAShareFeeExecutionBindingFailureV2
```

It computes canonical Order/hash, derives every output field, performs no registry lookup, and rejects before producing a binding when Order account, Venue, Instrument, side, trade context, or created instant does not match `authority.scope`.

`CnAShareFeeExecutionBindingFailureCodeV2` exact first-applicable order is:

1. `AUTHORITY_SCOPE_MISMATCH = "authority_scope_mismatch"`
2. `ORDER_ACCOUNT_MISMATCH = "order_account_mismatch"`
3. `ORDER_VENUE_MISMATCH = "order_venue_mismatch"`
4. `ORDER_INSTRUMENT_MISMATCH = "order_instrument_mismatch"`
5. `ORDER_SIDE_MISMATCH = "order_side_mismatch"`
6. `ORDER_CONTEXT_MISMATCH = "order_context_mismatch"`

Authority scope mismatch reconstructs Scope/hash and repeated Authority values; account/Venue/Instrument compare the exact Order to Scope; side requires `order.intent.side in scope.allowed_order_sides`; context requires `scope.coverage_from <= order.created_at.instant < scope.coverage_to_exclusive` together with Scope CNY currencies/type and Auction mechanism.

`CnAShareFeeExecutionBindingFailureV2` exact fields are `authority: CnAShareFeeExecutionAuthorityV2`, `authority_hash: str`, `scope: CnAShareFeeExecutionScopeV2`, `scope_hash: str`, `order: Order`, `order_hash: str`, `code: CnAShareFeeExecutionBindingFailureCodeV2`, and `subject_ids: tuple[str, ...]`, in that order. Its type is `cn_a_share_fee_execution_binding_failure_v2`; `failure_hash` is derived. Its fixed subject prefix is exactly `(code.value, authority_hash, scope_hash, order_hash)`, followed only by the code-specific suffix below; no subject tuple is deduplicated or sorted.

| code | exact suffix in order |
| --- | --- |
| `AUTHORITY_SCOPE_MISMATCH` | `("authority_scope_hash", authority.scope_hash, "authority_selection_hash", authority.selection_hash)` |
| `ORDER_ACCOUNT_MISMATCH` | `("order_account_id", order.account_id, "scope_account_id", scope.account_id)` |
| `ORDER_VENUE_MISMATCH` | `("order_venue_id", order.intent.instrument_id.venue.value, "scope_venue_id", scope.venue_id.value)` |
| `ORDER_INSTRUMENT_MISMATCH` | `("order_instrument_id", str(order.intent.instrument_id), "scope_instrument_id", str(scope.instrument_id))` |
| `ORDER_SIDE_MISMATCH` | `("order_side", order.intent.side.value, "allowed_order_sides_hash", canonical_sha256(scope.allowed_order_sides))` |
| `ORDER_CONTEXT_MISMATCH` | `("order_created_at_hash", canonical_sha256(order.created_at.instant), "scope_coverage_from_hash", canonical_sha256(scope.coverage_from), "scope_coverage_to_exclusive_hash", canonical_sha256(scope.coverage_to_exclusive), "scope_trade_mechanism", scope.trade_mechanism.value)` |

All labels are literal strings; Order IDs are contained in canonical `order_hash`, Venue/enum values use `.value`, and every `*_hash` is canonical `sha256:` text. Therefore `failure_hash = canonical_sha256(failure body)` is unique and reproducible.

`CnAShareCashFeeRuleQueryV2` exact fields, in order, are `authority: CnAShareFeeExecutionAuthorityV2`, `authority_hash: str`, `execution_binding: CnAShareFeeExecutionBindingV2`, `binding_hash: str`, `purpose: CnAShareFeeAssessmentPurposeV2`, `fill: Fill | None`, `fill_hash: str | None`, and `fill_id: DomainId | None`. Its canonical type is `cn_a_share_cash_fee_rule_query_v2`; its body contains those fields followed by derived `order_id`, `order_hash`, `account_id`, `venue_id`, `instrument_id`, `side`, and `effective_at`, in that order; `query_hash = canonical_sha256(body)`. Its direct constructor enforces only exact types, canonical hash form, and `fill_id.kind == FILL` when present.

The only positional-only query constructors are:

```python
CnAShareCashFeeRuleQueryV2.for_reservation(authority, execution_binding, /)
CnAShareCashFeeRuleQueryV2.for_final_fill(authority, execution_binding, fill, /)
```

They return `CnAShareCashFeeRuleQueryV2 | CnAShareFeeQueryConstructionFailureV2`. Reservation requires exact Authority/binding identity, sets `purpose=RESERVATION`, all Fill fields to `None`, and derives side/effective time from the bound Order (`order.intent.side`, `order.created_at.instant`). Final requires exact Fill, stores its canonical hash/ID, and derives effective time only from `fill.execution_time`; no constructor accepts a caller side/time.

`CnAShareFeeQueryConstructionFailureCodeV2` exact first-applicable order is:

1. `AUTHORITY_BINDING_MISMATCH = "authority_binding_mismatch"`
2. `RESERVATION_CONTEXT_MISMATCH = "reservation_context_mismatch"`
3. `MISSING_FILL = "missing_fill"`
4. `FILL_ORDER_MISMATCH = "fill_order_mismatch"`
5. `FILL_ACCOUNT_MISMATCH = "fill_account_mismatch"`
6. `FILL_VENUE_MISMATCH = "fill_venue_mismatch"`
7. `FILL_INSTRUMENT_MISMATCH = "fill_instrument_mismatch"`
8. `FILL_SIDE_MISMATCH = "fill_side_mismatch"`
9. `EXECUTION_TIME_MISMATCH = "execution_time_mismatch"`

Authority/binding mismatch compares authority hash and binding reconstruction; reservation context requires bound Order side/time still reconstruct. `MISSING_FILL` is evaluated before any Fill dereference whenever final construction receives `fill is None`. Later final codes compare exact Fill Order ID, account, Venue, Instrument, side, then require exactly `binding.order_effective_at <= fill.execution_time < authority.scope.coverage_to_exclusive`; either lower- or upper-bound violation is `EXECUTION_TIME_MISMATCH`. `CnAShareFeeQueryConstructionFailureV2` exact fields are `authority: CnAShareFeeExecutionAuthorityV2`, `authority_hash: str`, `execution_binding: CnAShareFeeExecutionBindingV2`, `binding_hash: str`, `purpose: CnAShareFeeAssessmentPurposeV2`, `fill: Fill | None`, `fill_hash: str | None`, `code: CnAShareFeeQueryConstructionFailureCodeV2`, and `subject_ids: tuple[str, ...]`, in that order. Its type is `cn_a_share_fee_query_construction_failure_v2`; `failure_hash` is derived. Its fixed subject prefix is exactly `(code.value, authority_hash, binding_hash, purpose.value, fill_hash or "none")`, followed only by the code-specific suffix below; no subject tuple is deduplicated or sorted.

| code | exact suffix in order |
| --- | --- |
| `AUTHORITY_BINDING_MISMATCH` | `("binding_authority_hash", execution_binding.authority_hash)` |
| `RESERVATION_CONTEXT_MISMATCH` | `("order_id", execution_binding.order_id.value, "order_hash", execution_binding.order_hash, "order_effective_at_hash", canonical_sha256(execution_binding.order_effective_at))` |
| `MISSING_FILL` | `("fill", "none")` |
| `FILL_ORDER_MISMATCH` | `("fill_order_id", fill.order_id.value, "binding_order_id", execution_binding.order_id.value)` |
| `FILL_ACCOUNT_MISMATCH` | `("fill_account_id", fill.account_id, "binding_account_id", execution_binding.account_id)` |
| `FILL_VENUE_MISMATCH` | `("fill_venue_id", fill.venue_id.value, "binding_venue_id", execution_binding.venue_id.value)` |
| `FILL_INSTRUMENT_MISMATCH` | `("fill_instrument_id", str(fill.instrument_id), "binding_instrument_id", str(execution_binding.instrument_id))` |
| `FILL_SIDE_MISMATCH` | `("fill_side", fill.side.value, "binding_side", execution_binding.side.value)` |
| `EXECUTION_TIME_MISMATCH` | `("fill_execution_time_hash", canonical_sha256(fill.execution_time), "binding_order_effective_at_hash", canonical_sha256(execution_binding.order_effective_at), "scope_coverage_to_exclusive_hash", canonical_sha256(authority.scope.coverage_to_exclusive))` |

`fill` is present for every final-code row and never represented by a wildcard; literals, `.value` IDs/enums, and canonical hash text use exactly the representations shown. Therefore `failure_hash = canonical_sha256(failure body)` is unique and reproducible.

### Bands, RuleBooks, policies, components, and quantization

`CnAShareMarketFeeBandV2` exact fields are `venue_id: VenueId`, `effective_from: UtcInstant`, `effective_to_exclusive: UtcInstant`, `handling_applies: bool`, `handling_rate: Rate`, `handling_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]`, `regulatory_applies: bool`, `regulatory_rate: Rate`, `regulatory_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]`, `chinaclear_transfer_applies: bool`, `chinaclear_transfer_rate: Rate`, `chinaclear_transfer_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]`, `hkscc_transfer_applies: bool`, `hkscc_transfer_rate: Rate`, and `hkscc_transfer_source_refs: tuple[CnAShareFeeRuleSourceRef, ...]`, in exactly that order. Its canonical type is `cn_a_share_market_fee_band_v2`; `band_hash` covers all fields. Intervals are finite, nonempty, half-open; rates are non-negative `fee_fraction`; false applies requires exact zero rate; every source-ref tuple is nonempty, canonical-sorted, and duplicate-free.

`CnAShareStampDutyBandV2` exact fields are `venue_id: VenueId`, `effective_from: UtcInstant`, `effective_to_exclusive: UtcInstant`, `applies_to_sell: bool`, `rate: Rate`, and `source_refs: tuple[CnAShareFeeRuleSourceRef, ...]`, in that order. Its canonical type is `cn_a_share_stamp_duty_band_v2`; the same interval/rate/source rules apply, and false sell applicability requires exact zero rate.

`CnAShareMarketFeeRuleBookV2` exact fields are `rule_book_key: str`, `rule_book_version: int`, `access_route: CnAShareExecutionAccessRoute`, `fee_product_class: CnAShareFeeProductClass`, and `bands: tuple[CnAShareMarketFeeBandV2, ...]`, in that order; its type is `cn_a_share_market_fee_rule_book_v2`. `CnAShareStampDutyRuleBookV2` exact fields are `rule_book_key: str`, `rule_book_version: int`, `access_route: CnAShareExecutionAccessRoute`, `fee_product_class: CnAShareFeeProductClass`, and `bands: tuple[CnAShareStampDutyBandV2, ...]`, in that order; its type is `cn_a_share_stamp_duty_rule_book_v2`. Both require `rule_book_version == 2`, derive `rule_book_hash = canonical_sha256(body)`, and sort Bands by Venue, half-open interval, then `band_hash`. They resolve only after authority/book route/product equality passes.

`CnAShareCashMarketFeePolicyV2` exact fields, in order, are `execution_semantic_binding: CnAShareFeeExecutionSemanticBindingV2`, `semantic_binding_hash: str`, `authority: CnAShareFeeExecutionAuthorityV2`, `authority_hash: str`, and `assessment_scale: Scale`; it exposes only `assess_fees(query: CnAShareCashFeeRuleQueryV2, /) -> ProfilePortOutcome[CnAShareMarketFeeRuleResolutionV2, CnAShareFeeRuleFailureV2]`. `CnAShareCashStampDutyTaxPolicyV2` exact fields, in order, are `execution_semantic_binding: CnAShareFeeExecutionSemanticBindingV2`, `semantic_binding_hash: str`, `authority: CnAShareFeeExecutionAuthorityV2`, `authority_hash: str`, and `assessment_scale: Scale`; it exposes only `assess_taxes(query: CnAShareCashFeeRuleQueryV2, /) -> ProfilePortOutcome[CnAShareStampDutyRuleResolutionV2, CnAShareFeeRuleFailureV2]`. Both require exact semantic-binding/hash, Authority/hash, proof/hash, and `Scale(2)` equality; they consume only the expected Authority book/ref and accept no RuleBook, side, time, route/product, or caller-selected expected hash argument.

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

`ProfileComponentRef.component_digest` is exactly `canonical_sha256` of the respective body; its `port_type` is `FEE_ASSESSMENT_POLICY` for market and `TAX_POLICY` for stamp duty. The authority builder—not a policy—owns component-ref construction failures.

Market generated charge keys and order are exactly:

```text
handling
securities_regulatory
chinaclear_transfer
hkscc_transfer
```

The only tax charge key is exactly `stamp_duty`. No generated v2 rule uses `exchange_handling`, `regulatory`, `transfer`, `market_fee_order_coverage`, or another key. ChinaClear and HKSCC never share a key, source tuple, or ID preimage.

For every generated `FeeReservationChargeRule` and `FinalFeeChargeRule`, the exact rule-ID preimage is:

```text
{
  type: "cn_a_share_fee_generated_rule_id_v2",
  schema_version: 1,
  rule_type,
  rule_schema_version: 1,
  component_key,
  component_version,
  component_digest,
  rule_book_hash,
  band_hash,
  authority_hash,
  binding_hash,
  query_hash,
  access_route,
  fee_product_class,
  charge_key,
  purpose,
  basis_type,
  applies,
  source_refs,
  quantization_version
}
```

`rule_type` is exactly `cn_a_share_market_fee_charge_rule_v2` for market and `cn_a_share_stamp_duty_charge_rule_v2` for tax. `purpose` is exactly `reservation`, `final_fill`, or `final_order`; `basis_type` is exactly `order_notional`, `fill`, or `order` for those purposes; `applies` is exact `bool`; `source_refs` is the exact nonempty canonical tuple from that charge Band; and `quantization_version` is the fixed market/tax version above. Tags are exactly `cn-a-share-market-fee-rule-v2` and `cn-a-share-stamp-duty-rule-v2`, followed by `:` plus `canonical_sha256(preimage)`.

For market reservation/final-fill, `applies` is the corresponding Band applies flag; for market final-order it is `False` for each of the four charge keys. For tax reservation/final-fill, `applies == (band.applies_to_sell and query.side is SELL)`; for tax final-order it is `False`. `True` maps to `FeeReservationApplicability.APPLIES` or `FinalFeeApplicability.ALWAYS`; `False` maps to `NOT_APPLICABLE` in both generic rule families. A false applies value has zero rate and remains a separate rule with its nonempty source refs; it is never an applied zero charge.

### Results, policy failures, and buffer

`CnAShareMarketFeeRuleResolutionV2` exact fields, in order, are `authority: CnAShareFeeExecutionAuthorityV2`, `authority_hash: str`, `query: CnAShareCashFeeRuleQueryV2`, `query_hash: str`, `binding_hash: str`, `order_id: DomainId`, `order_hash: str`, `fill: Fill | None`, `fill_hash: str | None`, `fill_id: DomainId | None`, `side: OrderSide`, `effective_at: UtcInstant`, `active_band: CnAShareMarketFeeBandV2`, `active_band_hash: str`, `reservation_charge_rules: tuple[FeeReservationChargeRule, ...]`, `final_fill_charge_rules: tuple[FinalFeeChargeRule, ...]`, and `final_order_not_applicable_rules: tuple[FinalFeeChargeRule, ...]`. Its type is `cn_a_share_market_fee_rule_resolution_v2`; `resolution_hash` covers every field. Every tuple has exactly the four market keys in the fixed order. Reservation has all Fill fields `None`; final Fill binds exact Fill/hash/ID. All derived identity/time fields reconstruct from the query.

`CnAShareStampDutyRuleResolutionV2` exact fields, in order, are `authority: CnAShareFeeExecutionAuthorityV2`, `authority_hash: str`, `query: CnAShareCashFeeRuleQueryV2`, `query_hash: str`, `binding_hash: str`, `order_id: DomainId`, `order_hash: str`, `fill: Fill | None`, `fill_hash: str | None`, `fill_id: DomainId | None`, `side: OrderSide`, `effective_at: UtcInstant`, `active_band: CnAShareStampDutyBandV2`, `active_band_hash: str`, `reservation_charge_rule: FeeReservationChargeRule`, `final_fill_charge_rule: FinalFeeChargeRule`, and `final_order_not_applicable_rule: FinalFeeChargeRule`. Its type is `cn_a_share_stamp_duty_rule_resolution_v2`; `resolution_hash` covers every field. Each tax rule has only `charge_key="stamp_duty"` and all identity/time fields reconstruct from the query.

After the required execution-authority match, policies canonically re-run the authoritative query constructor before any remaining policy-owned check: `RESERVATION` invokes `CnAShareCashFeeRuleQueryV2.for_reservation(query.authority, query.execution_binding, /)`; `FINAL_FILL` invokes `CnAShareCashFeeRuleQueryV2.for_final_fill(query.authority, query.execution_binding, query.fill, /)`. The result must be a successful query exactly equal to the supplied query with the same `query_hash`; a constructor failure, absent final Fill, wrong Fill/order/account/Venue/Instrument/side/time, `dataclasses.replace`, or `object.__new__` bypass is not repaired or reinterpreted. A structurally valid direct `FINAL_FILL` query with `fill=None` deterministically produces constructor `MISSING_FILL` and therefore policy `QUERY_PROVENANCE_MISMATCH`, never a Fill dereference.

`CnAShareFeeRuleFailureCodeV2` is limited to semantically reachable policy failures in this exact order:

1. `EXECUTION_AUTHORITY_MISMATCH = "execution_authority_mismatch"`
2. `QUERY_PROVENANCE_MISMATCH = "query_provenance_mismatch"`
3. `AUTHORITY_QUERY_MISMATCH = "authority_query_mismatch"`
4. `RULE_BOOK_SCOPE_MISMATCH = "rule_book_scope_mismatch"`
5. `MISSING_RULE_INTERVAL = "missing_rule_interval"`
6. `OVERLAPPING_RULE_INTERVALS = "overlapping_rule_intervals"`

Before query use, `EXECUTION_AUTHORITY_MISMATCH` requires policy Authority/hash/proof and query Authority/hash/proof to exact-match the execution-selected semantic binding's Authority/hash/proof. A directly constructed Authority that is structurally valid but is not the selected expected Authority/proof fails here. The policy then performs `QUERY_PROVENANCE_MISMATCH` reconstruction; `AUTHORITY_QUERY_MISMATCH` compares the successful reconstructed query authority/hash to policy authority/hash; `RULE_BOOK_SCOPE_MISMATCH` checks Authority Scope/selection/books/component refs as an inseparable pair; only then does the policy resolve intervals.

`CnAShareFeeRuleFailureV2` exact fields are `query: CnAShareCashFeeRuleQueryV2`, `query_hash: str`, `code: CnAShareFeeRuleFailureCodeV2`, and `subject_ids: tuple[str, ...]`, in that order. Its type is `cn_a_share_fee_rule_failure_v2`; `failure_hash` is derived. Its fixed subject prefix is exactly `(code.value, policy.authority_hash, query.query_hash)`, followed only by the code-specific suffix below; no subject tuple is deduplicated or sorted.

| code | exact suffix in order |
| --- | --- |
| `EXECUTION_AUTHORITY_MISMATCH` | `("query_authority_hash", query.authority_hash, "policy_authority_hash", policy.authority_hash, "expected_authority_hash", policy.execution_semantic_binding.authority_hash, "query_profile_binding_hash", query.authority.profile_binding_hash, "policy_profile_binding_hash", policy.authority.profile_binding_hash, "expected_profile_binding_hash", policy.execution_semantic_binding.profile_binding_hash)` |
| `QUERY_PROVENANCE_MISMATCH` | `("purpose", query.purpose.value, "reconstructed_query_hash", reconstructed.query_hash)` on successful reconstruction; otherwise `("purpose", query.purpose.value, "query_construction_failure_hash", reconstruction_failure.failure_hash)` |
| `AUTHORITY_QUERY_MISMATCH` | `("query_authority_hash", query.authority_hash, "policy_authority_hash", policy.authority_hash)` |
| `RULE_BOOK_SCOPE_MISMATCH` | `("scope_hash", query.authority.scope_hash, "market_fee_rule_book_hash", query.authority.market_fee_rule_book_hash, "stamp_duty_rule_book_hash", query.authority.stamp_duty_rule_book_hash)` |
| `MISSING_RULE_INTERVAL` | `("venue_id", query.venue_id.value, "effective_at_hash", canonical_sha256(query.effective_at), "rule_book_hash", selected_rule_book.rule_book_hash, "active_band_hashes_hash", canonical_sha256(()))` |
| `OVERLAPPING_RULE_INTERVALS` | `("venue_id", query.venue_id.value, "effective_at_hash", canonical_sha256(query.effective_at), "rule_book_hash", selected_rule_book.rule_book_hash, "active_band_hashes_hash", canonical_sha256(tuple(sorted(band.band_hash for band in active_bands))) )` |

`reconstructed`, `reconstruction_failure`, `selected_rule_book`, and `active_bands` are the named local values from the immediately preceding prescribed operation; they never mean caller-selected IDs. All labels are literal strings; `.value` is used for enums/Venue, and all hashes are canonical `sha256:` text. Therefore `failure_hash = canonical_sha256(failure body)` is unique and reproducible. Policies return no partial rules.

`CnAShareFeeReservationBufferV2` exact fields, in order, are `market_resolution: CnAShareMarketFeeRuleResolutionV2`, `tax_resolution: CnAShareStampDutyRuleResolutionV2`, `maximum_fill_count: int`, `market_charge_rule: FeeReservationChargeRule`, and `tax_charge_rule: FeeReservationChargeRule`. Its type is `cn_a_share_fee_reservation_buffer_v2`; `buffer_hash` is derived. It accepts reservation resolutions only, exact-matching authority/scope/binding/query/order/side/effective time, and a positive count.

Let `u = floor(maximum_fill_count / 2)`. `market_component_count` is exactly the count of true applies flags among the four active market Band charges; `tax_component_count` is `1` exactly when `band.applies_to_sell and query.side is SELL`, otherwise `0`. The market buffer is `Money(market_component_count * u, Scale(2), "CNY")`; the tax buffer is `Money(tax_component_count * u, Scale(2), "CNY")`. A zero count is `NOT_APPLICABLE`, carries exactly `Money(0, Scale(2), "CNY")`, and still derives its own v2 rule identity. Domestic ordinary has market count 3; a separately evidenced Northbound ordinary book with HKSCC applicable has 4. Account commission/minimum never enters this type.

The market/tax buffer tags are exactly `cn-a-share-market-fee-rounding-buffer-v2` and `cn-a-share-tax-rounding-buffer-v2`. The exact buffer rule-ID preimage is:

```text
{
  type: "cn_a_share_fee_reservation_buffer_rule_id_v2",
  schema_version: 1,
  rule_type: "cn_a_share_fee_reservation_buffer_rule_v2",
  rule_schema_version: 1,
  component_key,
  component_version,
  component_digest,
  authority_hash,
  scope_hash,
  binding_hash,
  market_resolution_hash,
  tax_resolution_hash,
  maximum_fill_count,
  component_count,
  applies,
  charge_key,
  basis_type: "flat_per_order",
  amount: Money(component_count * floor(maximum_fill_count / 2), Scale(2), "CNY"),
  quantization_version: "cn-a-share-fee-reservation-buffer.cny-cent.half-up.v2"
}
```

For the market buffer `charge_key="handling"` and `component_count=market_component_count`; for tax it is `charge_key="stamp_duty"` and `component_count=tax_component_count`. `applies == (component_count > 0)`. Actual Fill count above the bound fails closed.

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
- No new Protocol, generic port, interface, generic registry, resolver, factory framework, DSL, callback, plugin, cache, provider adapter, Runtime market branch, or second fee engine. The one named private v2 profile/build registration is the sole additive exception.
- Kernel concrete-profile code may import v1 sibling types only for the pure projection. Generic Kernel modules never import concrete A-share code.
- Runtime profile-authority/profile-build binding is private, profile-specific, and isolated; only the named v2 registration carries its hashes into the v2-only semantic preimage. Engine, Runner, composition, financial dispatch, and resolution remain free of A-share branches for v1 and receive no A-share name matching.
- Builder imports neither Kernel nor Runtime. This slice adds no Builder code.
- V2 Kernel names are concrete-submodule public; existing `cn_a_share.__all__` v1 members/order remain exact and only the declared v2 names append. The private Runtime helper and both package roots remain unchanged. Existing G08H root import set remains exact.
- Production never imports `tests.support`; test support never becomes semantic authority.

## Staged delivery

### F0 — contract freeze — this change

Accept ADR 0005, freeze this plan, add glossary terms, and update G12H status/sequence. No implementation artifacts.

### F1 — contract RED

Add only the additive tests and expected fixture bodies listed above. RED must fail because the v2 symbols/modules do not exist, while all v1 tests and protected-byte assertions pass. Do not modify production code in the RED commit.

### F2 — Kernel GREEN

Implement only `commission_tax_v2.py` and concrete submodule exports: exact Scope, selection, authority, structured binder/query-construction failures, Order binding, authoritative reservation/final query constructors, policy query-provenance reconstruction, results/failures/buffer, and XSHE-only compatibility projection. Make kernel RED/golden tests pass. Rerun all G08E v1 tests and byte locks.

### F3 — private profile-authority binding GREEN

Implement only `cn_a_share_fee_v2.py` and the additive test-support module. Make `_create_cn_a_share_fee_execution_authority_v2(resolved_profile, scope, selection, /)` reconstruct `CnAShareFeeProfileBindingProofV2`; then create the one new `equity.cn_a_share.fee-execution.v2` private profile/build registration that binds Authority/proof hashes into v2 financial semantic and Semantic Run inputs. It must reject swapped expected Authority/proof before execution without modifying v1 composer, registry entries, root exports, existing journey, or fixture bytes.

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

- an explicit Scope and selection plus the successful frozen G08H profile yield one stable authority/hash; mutating Scope account/Venue/Instrument/type/currency/mechanism/side/profile fact, resolved-profile/request/declaration identity, component ref/digest, book body/hash, route, or product changes it;
- the private builder owns and tests every authority-build failure in its declared order; it rejects non-XSHE/non-CNY/non-Auction/non-domestic/non-ordinary/Stock-Connect/ineligible-v1 Scope and never manufactures route/product;
- an authority cannot pair either of its books with another authority, including equal-rate/equal-scope books;
- binder owns and tests authority-Scope, Order account/Venue/Instrument/side/context failures in its declared order and returns no binding; it performs no registry lookup;
- reservation constructor accepts no side/time and uses bound Order side/created instant; final constructor accepts no side/time and uses exact Fill side/execution time;
- query construction owns and tests `MISSING_FILL` before Fill dereference, then final Fill Order/account/Venue/Instrument/side and lower-or-upper-bound execution-time failures in its declared order, returning no query; direct `FINAL_FILL` `fill=None` reaches policy only as `QUERY_PROVENANCE_MISMATCH`;
- policy first checks execution-selected Authority/proof, then re-runs the authoritative query constructor and tests `QUERY_PROVENANCE_MISMATCH`, then authority/query mismatch, RuleBook scope mismatch, and interval gap/overlap; symbol/stable-key mutations do not infer route/product; omitted route/product is a construction error.

### Economic and component controls

- XSHE-only finite v1 projection preserves exact interval/rate/source economics for handling, regulatory, ChinaClear, and stamp duty; any XSHG source Band rejects before output construction;
- every v2 source-ref tuple is nonempty; compatibility HKSCC not-applicability has its deterministic interval/source-book-derived ref;
- projection creates new selection/authority/query/book/component/rule/resolution hashes even when monetary outputs match v1;
- domestic ordinary result has four market rules keyed `handling`, `securities_regulatory`, `chinaclear_transfer`, `hkscc_transfer`, with HKSCC explicitly not applicable and nonempty provenance;
- Northbound ordinary control requires a separate book and can carry ChinaClear plus HKSCC simultaneously;
- ChinaClear and HKSCC source/rule IDs remain distinct under equal rates, zero rates, reorder attempts, and source mutation; stamp duty uses only `stamp_duty`;
- all purposes have exact applies bool/mapping; NOT_APPLICABLE uses zero rate/zero buffer amount and retains a separate source-bound rule identity;
- preferred and ETF books do not resolve through ordinary books;
- ETF waiver controls are not-applicable rules, not applied zero charges;
- every Fill resolves by its execution time; no acceptance-time or first-Fill reuse;
- gap/overlap remains finite and fail closed.

### Precedence and atomicity controls

- each failure belongs to exactly one seam: builder, binder, query constructor, or policy; structural/canonical forgery is constructor-rejected;
- multi-defect inputs return the exact first failure order and exact subject_ids at their owning seam;
- builder precedes binder; binder precedes query construction; policy starts with execution-selected Authority/proof mismatch, then query provenance, authority/query mismatch, RuleBook scope mismatch, gap, overlap;
- every failure returns no authority, binding, query, reservation/final rules, or projection as applicable.

### Reservation/final controls

- domestic ordinary `maximum_fill_count=2` has market `Money(3, Scale(2), "CNY")` and a new v2 scope/authority/binding/query/buffer/rule identity;
- a separately evidenced Northbound ordinary control uses four applicable market components;
- BUY stamp duty is NOT_APPLICABLE with `Money(0, Scale(2), "CNY")`; SELL behavior follows the v2 tax Band;
- buffer component_count counts only applicable charges and exact Money/charge-key/applies/source fields enter the buffer preimage;
- final resolution canonically binds exact Fill, Fill hash, Fill ID, derived side, and `Fill.execution_time`;
- Fill-count overflow fails closed; generic estimator/assessment/Journal outputs require no A-share branch.

### Canonical and forgery controls

- canonical input reorder normalizes where declared; semantic order remains fixed where declared;
- forged selection/authority/binding/query/fill hash, Band hash, RuleBook hash, component ref/digest, resolution rules/order/Fill context, projection source/output hash, and buffer hash are rejected; direct constructor, `dataclasses.replace`, and `object.__new__` query bypasses fail policy `QUERY_PROVENANCE_MISMATCH` atomically;
- mutation of route/product/applies/source/rate/interval/profile/request/order/Fill/component/proof/profile-build context propagates through all v2 identities; swapped structurally valid Authority/proof changes v2 request/Semantic Run identity and is rejected before execution;
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
