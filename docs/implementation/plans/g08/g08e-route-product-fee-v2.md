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

The implementation contract is not `PASSED`. G12H F1 remains blocked until the RED contract is implemented and passes all compatibility, semantic, architecture, and byte-lock checks.

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

`cn_a_share_fee_v2.py` is a pure binding seam. It may import domain `Order`, v1 `CnAShareResolvedProfile`, and the v2 Kernel binding/enums. It imports no Engine, Runner, Builder, provider, repository, filesystem, network, database, process, wall clock, callback, or implementation object identity. It is not imported or exported by `crypto_quant_backtest.__init__`.

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

All dataclasses are frozen and slotted. Every additive canonical type starts its own `schema_version=1` lineage and uses a type literal ending `_v2`. Derived hashes are properties, excluded from their own preimages, and recomputed by constructors where the body is reconstructable.

The following symbols are exported only from `crypto_quant_trading.profiles.cn_a_share`:

- `CnAShareExecutionAccessRoute`
- `CnAShareFeeProductClass`
- `CnAShareFeeExecutionBindingV2`
- `CnAShareCashFeeRuleQueryV2`
- `CnAShareMarketFeeBandV2`
- `CnAShareMarketFeeRuleBookV2`
- `CnAShareStampDutyBandV2`
- `CnAShareStampDutyRuleBookV2`
- `CnAShareMarketFeeRuleResolutionV2`
- `CnAShareStampDutyRuleResolutionV2`
- `CnAShareFeeRuleFailureCodeV2`
- `CnAShareFeeRuleFailureV2`
- `CnAShareCashMarketFeePolicyV2`
- `CnAShareCashStampDutyTaxPolicyV2`
- `CnAShareFeeReservationBufferV2`
- `CnAShareDomesticOrdinaryFeeProjectionV2`
- `project_cn_a_share_domestic_ordinary_fee_rules_v2`

No symbol is exported from the global `crypto_quant_trading` root.

### Enums

Exact values and declaration order:

```python
class CnAShareExecutionAccessRoute(str, Enum):
    DOMESTIC = "domestic"
    NORTHBOUND_STOCK_CONNECT = "northbound_stock_connect"

class CnAShareFeeProductClass(str, Enum):
    ORDINARY_A_SHARE = "ordinary_a_share"
    PREFERRED_STOCK = "preferred_stock"
    ETF = "etf"
```

No enum member, query field, binding field, RuleBook field, policy argument, or factory parameter has a default. `InstrumentType.EQUITY`, symbol text, stable key, board, account permission, and current metadata never infer either enum.

### Immutable profile/order execution binding

`CnAShareFeeExecutionBindingV2` exact fields, in order:

1. `market_profile_key: str`
2. `market_profile_version: int`
3. `market_profile_digest: str`
4. `execution_account_profile_key: str`
5. `execution_account_profile_version: int`
6. `execution_account_profile_digest: str`
7. `instrument_scope_declaration_hash: str`
8. `account_scope_declaration_hash: str`
9. `order_id: DomainId`
10. `account_id: str`
11. `venue_id: VenueId`
12. `instrument_id: InstrumentId`
13. `access_route: CnAShareExecutionAccessRoute`
14. `fee_product_class: CnAShareFeeProductClass`

Canonical body:

```text
{
  type: "cn_a_share_fee_execution_binding_v2",
  schema_version: 1,
  market_profile_key,
  market_profile_version,
  market_profile_digest,
  execution_account_profile_key,
  execution_account_profile_version,
  execution_account_profile_digest,
  instrument_scope_declaration_hash,
  account_scope_declaration_hash,
  order_id,
  account_id,
  venue_id,
  instrument_id,
  access_route,
  fee_product_class
}
```

`binding_hash = canonical_sha256(body)`. Exact positive versions, canonical text/hash values, `order_id.kind == ORDER`, and `instrument_id.venue == venue_id` are constructor invariants.

The Runtime module exposes one positional-only pure operation from its own module, not the package root:

```python
bind_cn_a_share_domestic_ordinary_fee_execution_v2(
    resolved_profile: CnAShareResolvedProfile,
    order: Order,
    /,
) -> CnAShareFeeExecutionBindingV2
```

It accepts only the frozen successful G08H profile scope: ordinary domestic standard cash auction, no Stock Connect, and matching Account/Venue/Instrument. It exact-binds the profile keys/digests, declaration hashes, Order ID, Account, Venue, and Instrument, then sets the two explicit enum values. Mismatch raises before a query exists. Future Northbound, preferred-stock, or ETF profile factories are separate work and cannot reuse this function.

### V2 query

`CnAShareCashFeeRuleQueryV2` exact fields:

1. `instrument: InstrumentDefinition`
2. `order_id: DomainId`
3. `account_id: str`
4. `side: OrderSide`
5. `effective_at: UtcInstant`
6. `trade_mechanism: CnAShareFeeTradeMechanism`
7. `execution_binding: CnAShareFeeExecutionBindingV2`

Canonical body type is `cn_a_share_cash_fee_rule_query_v2`. `query_hash = canonical_sha256(body)`. Constructor validation is exact-type/canonical-form only; semantic mismatches remain structured policy failures.

A caller builds reservation queries from the approved Order and final Fill queries from the Fill plus its immutable source Order/binding. Every Fill retains the original binding but uses its own execution time, preserving v1 per-Fill historical resolution semantics.

### V2 market fee Band and RuleBook

`CnAShareMarketFeeBandV2` exact fields:

1. `venue_id`
2. `effective_from`
3. `effective_to_exclusive`
4. `handling_applies`
5. `handling_rate`
6. `handling_source_refs`
7. `regulatory_applies`
8. `regulatory_rate`
9. `regulatory_source_refs`
10. `chinaclear_transfer_applies`
11. `chinaclear_transfer_rate`
12. `chinaclear_transfer_source_refs`
13. `hkscc_transfer_applies`
14. `hkscc_transfer_rate`
15. `hkscc_transfer_source_refs`

Canonical type is `cn_a_share_market_fee_band_v2`; `band_hash` covers every field. Each applies field is exact `bool`; each rate is non-negative `fee_fraction`. `applies=False` requires an exact zero rate. Source refs are canonical-sorted and duplicate-free; they may be empty only for an explicit not-applicable component introduced by the compatibility projection. Evidence-built books retain nonempty not-applicability/waiver refs where authority exists.

`CnAShareMarketFeeRuleBookV2` exact fields:

1. `rule_book_key`
2. `rule_book_version`
3. `access_route`
4. `fee_product_class`
5. `bands`

Canonical type is `cn_a_share_market_fee_rule_book_v2`. `rule_book_version` is exactly `2`. Bands canonical-sort by Venue, half-open interval, and `band_hash`. The book resolves only by Venue and time after exact route/product equality has passed.

Generated market charge order is always:

```text
exchange_handling
securities_regulatory
chinaclear_transfer
hkscc_transfer
```

Reservation and final-Fill results contain four rules in that order. A false applies flag generates `NOT_APPLICABLE`, never an applied zero line. ChinaClear and HKSCC never share a charge key, source tuple, rule ID, or aggregate preimage.

### V2 stamp-duty Band and RuleBook

`CnAShareStampDutyBandV2` exact fields:

1. `venue_id`
2. `effective_from`
3. `effective_to_exclusive`
4. `applies_to_sell`
5. `rate`
6. `source_refs`

Canonical type is `cn_a_share_stamp_duty_band_v2`. False applicability requires zero rate. `CnAShareStampDutyRuleBookV2` has the same five fields/order and version rule as the market book, with canonical type `cn_a_share_stamp_duty_rule_book_v2`.

### Policy and generated-rule identities

Exact component identities:

```text
market component_key:     equity.cn_a_share.cash.market-fees.route-product.v2
market component_version: 2
market algorithm_key:     cn-a-share-historical-market-fees-route-product-v2

tax component_key:        equity.cn_a_share.cash.stamp-duty.route-product.v2
tax component_version:    2
tax algorithm_key:        cn-a-share-historical-stamp-duty-route-product-v2
```

Each component digest preimage is exact:

```text
{
  type,
  schema_version: 1,
  component_key,
  component_version: 2,
  algorithm_key,
  rule_book_hash,
  access_route,
  fee_product_class,
  assessment_scale: 2,
  rounding: "half_up"
}
```

Generated rule tags are:

```text
cn-a-share-market-fee-rule-v2
cn-a-share-stamp-duty-rule-v2
cn-a-share-market-fee-rounding-buffer-v2
cn-a-share-tax-rounding-buffer-v2
```

A generated market/tax rule ID preimage includes component key/version, RuleBook hash, Band hash, route, product, charge key, purpose, basis type, applies state, and exact source refs. Closure, projection, publication, profile, capture, receipt, path, and wall-clock identities do not enter execution rule IDs.

### Resolutions, failure, and precedence

`CnAShareMarketFeeRuleResolutionV2` mirrors the v1 market resolution identity fields, but carries the v2 query/book scope, four reservation rules, four final-Fill rules, and one final-Order not-applicable coverage rule. Canonical type is `cn_a_share_market_fee_rule_resolution_v2`.

`CnAShareStampDutyRuleResolutionV2` mirrors the v1 tax resolution with v2 query/book scope. Canonical type is `cn_a_share_stamp_duty_rule_resolution_v2`.

Both resolution hashes bind the full query and `query_hash`, route/product book identity, active Band/body hash, and all generated rules. Constructor reconstruction rejects query, binding, Band, source, applies-state, rule-order, or hash substitution.

`CnAShareFeeRuleFailureCodeV2` exact declaration and first-applicable order:

1. `UNSUPPORTED_VENUE = "unsupported_venue"`
2. `UNSUPPORTED_INSTRUMENT = "unsupported_instrument"`
3. `UNSUPPORTED_CURRENCY = "unsupported_currency"`
4. `UNSUPPORTED_TRADE_MECHANISM = "unsupported_trade_mechanism"`
5. `EXECUTION_BINDING_MISMATCH = "execution_binding_mismatch"`
6. `ROUTE_PRODUCT_MISMATCH = "route_product_mismatch"`
7. `MISSING_RULE_INTERVAL = "missing_rule_interval"`
8. `OVERLAPPING_RULE_INTERVALS = "overlapping_rule_intervals"`

Binding mismatch means the query Order, Account, Venue, or Instrument differs from the immutable binding. Route/product mismatch means the binding differs from either selected RuleBook. Missing or overlapping intervals are evaluated only after all scope checks pass.

`CnAShareFeeRuleFailureV2` exact fields are `query`, `query_hash`, and `code`; canonical type is `cn_a_share_fee_rule_failure_v2`. Policies return existing `ProfilePortOutcome`, exactly one result/failure, and no partial rules.

### Reservation buffer

`CnAShareFeeReservationBufferV2` keeps the v1 shape with v2 resolutions and rule identities. Let `u=floor(maximum_fill_count/2)` CNY cents, `m` be the count of applicable market components in the resolved Band, and `t` be one only when stamp duty applies to the query side. The exact buffers are `m*u` market cents and `t*u` tax cents.

For `DOMESTIC + ORDINARY_A_SHARE`, `m=3`; for a separately evidenced Northbound ordinary-A-share book with HKSCC applicable, `m=4`. Actual Fill count above the positive caller-supplied bound fails closed exactly as v1. No account commission/minimum enters this type.

## Finite v1-to-v2 compatibility projection

One pure positional-only function is allowed:

```python
project_cn_a_share_domestic_ordinary_fee_rules_v2(
    market_rule_book: CnAShareMarketFeeRuleBook,
    stamp_duty_rule_book: CnAShareStampDutyRuleBook,
    /,
) -> CnAShareDomesticOrdinaryFeeProjectionV2
```

It maps every finite v1 Band without extending, coalescing, or reinterpreting intervals:

- v1 handling -> v2 handling, applies true;
- v1 regulatory -> v2 regulatory, applies true;
- v1 transfer -> v2 ChinaClear transfer, applies true;
- v2 HKSCC transfer -> not applicable, exact zero rate, empty compatibility-only refs;
- v1 stamp duty -> v2 stamp duty, applies to sell true.

Output books are exact `DOMESTIC + ORDINARY_A_SHARE`, version `2`, with keys:

```text
equity.cn_a_share.cash.market-fees.domestic.ordinary-a-share.projected-v2
equity.cn_a_share.cash.stamp-duty.domestic.ordinary-a-share.projected-v2
```

`CnAShareDomesticOrdinaryFeeProjectionV2` exact fields:

1. `algorithm_id` fixed to `cn-a-share-domestic-ordinary-v1-to-v2-fee-projection-v1`
2. `source_market_rule_book`
3. `source_market_rule_book_hash`
4. `source_stamp_duty_rule_book`
5. `source_stamp_duty_rule_book_hash`
6. `access_route`
7. `fee_product_class`
8. `market_fee_rule_book`
9. `market_fee_rule_book_hash`
10. `stamp_duty_rule_book`
11. `stamp_duty_rule_book_hash`

Canonical type is `cn_a_share_domestic_ordinary_fee_projection_v2`; `projection_hash` is derived. This projection is a compatibility proof only. It does not establish new official evidence, open-ended continuity, July-2026 coverage, provider qualification, or a Northbound/preferred/ETF book.

## Architecture and public rules

- Reuse existing generic `FeeAssessmentPolicy`, `TaxPolicy`, `ProfilePortOutcome`, `FeeReservationEstimator`, `FeeAssessmentEngine`, RuleSet, Journal, and Ledger contracts unchanged.
- No new Protocol, generic port, interface, registry, resolver, factory framework, DSL, callback, plugin, cache, provider adapter, Runtime market branch, or second fee engine.
- Kernel concrete-profile code may import v1 sibling types only for the pure projection. Generic Kernel modules never import concrete A-share code.
- Runtime binding is profile-specific and isolated; Engine, Runner, composition, financial dispatch, and resolution remain free of A-share branches.
- Builder imports neither Kernel nor Runtime. This slice adds no Builder code.
- V2 Kernel names are concrete-submodule public. Runtime binding is direct-module public only. Existing G08H root import set remains exact.
- Production never imports `tests.support`; test support never becomes semantic authority.

## Staged delivery

### F0 — contract freeze — this change

Accept ADR 0005, freeze this plan, add glossary terms, and update G12H status/sequence. No implementation artifacts.

### F1 — contract RED

Add only the additive tests and expected fixture bodies listed above. RED must fail because the v2 symbols/modules do not exist, while all v1 tests and protected-byte assertions pass. Do not modify production code in the RED commit.

### F2 — Kernel GREEN

Implement only `commission_tax_v2.py` and concrete submodule exports. Make kernel RED/golden tests pass. Rerun all G08E v1 tests and byte locks.

### F3 — profile/order binding GREEN

Implement only `cn_a_share_fee_v2.py` and the additive test-support module. Make Runtime binding tests pass without modifying the v1 composer, root exports, existing journey, or fixture bytes.

### F4 — contract acceptance

Run focused/full validation, architecture/import checks, protected-byte locks, canonical mutation tests, mypy, lock/diff/gitleaks/status checks, and independent review. Only then set this contract `PASSED` in a separate authorized status change.

### F5 — G12H F1 resume

After F4 passes, G12H may resume source acquisition for `DOMESTIC + ORDINARY_A_SHARE` only. G12H remains responsible for July-2026 successor closure, target projection, publication, and coverage analysis. It must use separately keyed effective-until-superseded v2 books, not the finite compatibility projection.

## RED matrix

### Public shape and no-default controls

- enum member names, values, and order are exact;
- every field/signature above is exact and has no default;
- v1 signatures, field lists, root imports, and `__all__` behavior remain exact;
- new canonical types use their own type literals and cannot serialize as v1.

### Binding and scope controls

- successful G08H profile + matching Order yields one stable binding/hash;
- changed profile digest, declaration hash, Order ID, Account, Venue, Instrument, route, or product changes binding identity;
- mismatched query Order/Account/Venue/Instrument returns `EXECUTION_BINDING_MISMATCH`;
- domestic binding against Northbound book, ordinary binding against preferred/ETF book, or market/tax books with different scope returns `ROUTE_PRODUCT_MISMATCH` before interval lookup;
- symbol/stable-key mutations do not infer route/product;
- omitted route/product is a construction error, never domestic/ordinary default.

### Economic and component controls

- finite v1 projection preserves exact interval/rate/source economics for handling, regulatory, ChinaClear, and stamp duty;
- projection creates new query/book/component/rule/resolution hashes even when monetary outputs match v1;
- domestic ordinary result has four market rules with HKSCC explicitly not applicable;
- Northbound ordinary control requires a separate book and can carry ChinaClear plus HKSCC simultaneously;
- ChinaClear and HKSCC source/rule IDs remain distinct under equal rates, zero rates, reorder attempts, and source mutation;
- preferred and ETF books do not resolve through ordinary books;
- ETF waiver controls are not-applicable rules, not applied zero charges;
- every Fill resolves by its execution time; no acceptance-time or first-Fill reuse;
- gap/overlap remains finite and fail closed.

### Precedence and atomicity controls

- each failure code is independently reachable;
- multi-defect inputs return the exact first failure order;
- binding mismatch precedes route/product mismatch;
- route/product mismatch precedes gap/overlap;
- failures return no partial reservation/final rules or projection.

### Reservation/final controls

- domestic ordinary `maximum_fill_count=2` keeps the v1 three-market-component buffer amount but has a new v2 buffer/rule identity;
- a separately evidenced Northbound ordinary control uses four market components;
- BUY stamp duty remains not applicable; SELL behavior follows the v2 tax Band;
- Fill-count overflow fails closed;
- generic estimator/assessment/Journal outputs require no A-share branch.

### Canonical and forgery controls

- canonical input reorder normalizes where declared; semantic order remains fixed where declared;
- forged `query_hash`, Band hash, RuleBook hash, resolution rules/order, projection source/output hash, and binding hash are rejected;
- mutation of route/product/applies/source/rate/interval/profile/order context propagates through all v2 identities;
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
gitleaks git --no-banner --redact --log-opts="--all"
git status --short
```

Link/semantic assertions additionally check every referenced path, ADR status, plan status, exact enum literals, exact charge order, explicit F1 dependency on contract `PASSED`, no contradictory full-envelope language in G12H, and no edits to prohibited files.

## G12H unblocking sequence

1. This plan remains `READY_FOR_CONTRACT_RED`; G12H F1 remains blocked.
2. Contract RED freezes exact failure/canonical/byte behavior.
3. Kernel and Runtime binding GREEN pass independently.
4. Contract acceptance proves protected bytes, architecture, and semantics; only then may status become `PASSED`.
5. G12H F1 acquires and closes official evidence only for `DOMESTIC + ORDINARY_A_SHARE` and the five explicit lineages, including HKSCC as route-not-applicable evidence.
6. G12H F2 creates separately keyed July-2026 effective-until-superseded v2 RuleBooks; it does not use the finite compatibility projection as authority.
7. G12H F3 publishes a new additive declaration/Bundle identity.
8. Only after F1-F3 pass may G12H analyzer RED resume; only analyzer GREEN may close the existing `COVERAGE_GAP / market_fees` result.

## Nonclaims and prohibited scope

This contract does not claim complete July-2026 evidence, provider/archive completeness, broker commission/minimum, bundled fees, rebates, VAT, official rounding parity, block/after-hours trading, B shares, funds, bonds, margin/short, non-CNY trading, account-statement parity, broader Stock Connect qualification, preferred-stock qualification, ETF qualification, live/current use, decision grade, or deployment authorization.

It does not model daily portfolio-value fees, CPI/SI/STI or other instruction fees, money settlement, safekeeping, collateral, corporate-action service, or other participant/state/message-based costs. Add those only after a separate basis/state contract is accepted.

Do not modify code, fixtures, registry, Acceptance Matrix, plan README, or publication artifacts in this docs freeze. Do not merge or push as part of the plan freeze.
