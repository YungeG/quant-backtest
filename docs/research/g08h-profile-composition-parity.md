# G08H Profile Composition and Parity Acceptance Record

## Verdict

G08H is **PASSED** at immutable implementation commit `e954be6bc1d46a3d3f399a3c3cf874a917894570`. The exact contract and static fixture bytes remain frozen, while the production composer, test-support dispatcher/Journey and parity tool/runner are implemented and accepted.

This Gate remains development-only. It does not prove external provider/archive completeness, real security/account classification, decision-grade eligibility or deployment authorization.

## Reused authorities

G08H composes rather than replaces:

- G08A Calendar/Session;
- G08B T+1 Settlement/Availability;
- G08C Quantity Lattice;
- G08D historical Order Rules/Price Limits;
- G08E Fee/Stamp Duty;
- G08F Corporate Action Entitlement;
- G08G Corporate Action Cash/Share accounting;
- G09H profile-neutral Financial Dispatcher, Engine, Runner, Journal/Ledger and Snapshot seams;
- WP-00C exact comparator and first-divergence rules;
- G10G/G10H composition and layered-scope-report patterns.

The production owner is one pure `crypto_quant_backtest.cn_a_share_profile` module. The development dispatcher/Journey remains in `tests/support/cn_a_share`; parity remains in `tools/parity/cn_a_share.py` and its runner. Generic Runtime code must not gain A-share branches.

## Scope declarations

Five new production values carry caller-supplied development evidence:

1. `CnAShareInstrumentScopeDeclaration` stores a full `InstrumentDefinition`, existing `CnAShareInstrumentRuleContext`, finite coverage, availability, explicit ordinary-domestic/cash-auction assertions, every excluded product/distribution flag, and source snapshot/manifest hashes.
2. `CnAShareAccountScopeDeclaration` stores Account/Venue, finite coverage, availability, explicit cash/domestic assertions, margin-short/Stock-Connect/available-margin exclusions, and source hashes.
3. `CnAShareAnnouncementRevisionSetDeclaration` stores the scoped corporate action, ordered linear revision chain, terminal/cancellation state, finite coverage, availability and source hashes.
4. `CnAShareRegisterRevisionSetDeclaration` stores the scoped account/position/register series, ordered linear revision chain, terminal state, finite coverage, availability and source hashes.
5. `CnAShareIdentityHistoryDeclaration` stores canonical scoped identity/payload-hash pairs for corporate actions, register snapshots and register revisions, plus coverage, availability and source hashes.

Hashes are derived properties, not caller-supplied self-hash fields. Constructors own malformed type/text/hash/interval rejection; supported scope, closure, cancellation, coverage, availability and conflicting reuse remain structured composer failures.

These values prove only internal consistency of supplied evidence. G12L/G12M retain external source completeness and real-market qualification.

## Frozen composer behavior

`CnAShareProfileComposer.compose(request, /)` consumes the five optional declarations plus exact G08 Calendar/rule books/Entitlements/G08G requests and a finite Timeline window. Optional declarations permit structured missing-authority outcomes; inherited authorities use exact concrete types.

The fifteen failure codes and precedence are:

`MISSING_INSTRUMENT_SCOPE` → `MISSING_ACCOUNT_SCOPE` → `MISSING_ANNOUNCEMENT_REVISION_SET` → `MISSING_REGISTER_REVISION_SET` → `MISSING_IDENTITY_HISTORY` → `INSTRUMENT_SCOPE_MISMATCH` → `ACCOUNT_SCOPE_MISMATCH` → `AUTHORITY_CONTEXT_MISMATCH` → `REVISION_CLOSURE_MISMATCH` → `CROSS_QUERY_IDENTITY_CONFLICT` → `TIMELINE_COVERAGE_MISMATCH` → `EVIDENCE_NOT_AVAILABLE` → `UNSUPPORTED_TAX_DISPOSITION` → `UNSUPPORTED_XSHG_SHARE_DELIVERY` → `COMPONENT_IDENTITY_CONFLICT`.

Failure embeds the Request and reconstructs the first failure; strict XOR Outcome and Resolved Profile constructors reject forged replacement values.

## Tax and venue boundary

G08G already rejects `APPLIED` and `DEFERRED_UNSUPPORTED` before any Journal/Lot effect. G08H v1 preserves `NOT_APPLICABLE`-only success and does not add deferred-tax Lot state. XSHG bonus/capitalization also remains unsupported; XSHG cash payment remains within inherited G08F/G08G scope when all other declarations match.

## Profile and dispatcher identity

The Market profile exact-covers all 12 `ProfilePortType` values; the Simulation profile exact-covers all six `SimulationPortType` values. Existing G08 component refs and generic cash/no-op refs are reused. Only two explicit manifest identities are composed for cash no-liquidation rules and CNY identity valuation; their canonical payloads/digests are frozen in the composition fixture.

A-share scheduled Corporate Actions require a profile-specific `FinancialDispatcherSpec` key, `equity.cn_a_share.cash-financial-dispatch.v1`. It reuses default cash component refs but binds the resolved model, manifests, operation keys, G08G request identities and limitations. It must not masquerade as the generic cash dispatcher spec.

All profile/registration outputs remain `development`, `decision_grade_eligible=false`, `profile_qualified=false`, and `deployment_authorized=false`.

## Runtime Journey boundary

The development dispatcher implements the existing G09H seam and uses only:

- `cn_a_share.corporate_action.cash_payment.v1`, phase 110;
- `cn_a_share.corporate_action.share_delivery.v1`, phase 120.

The Journey freezes the existing XSHE CNY 70 payment and 210-share delivery, exact 7,500.00 CNY Lot basis conservation, full/prefix/resume Journal/Ledger/Lot reconstruction and Snapshot binding. G08A–G08F component semantics remain covered by their immutable inherited fixtures and are rerun in G08H acceptance rather than reimplemented by a second validator.

## Legacy scope/parity conclusion

The frozen `cycle-rotation-platform` archive contains budgeting and order-intent code but no authoritative exchange Calendar, historical Price Limit, exact Fee/Tax, T+1 availability, Corporate Action lifecycle or canonical Journal/Ledger semantics.

The G08H parity fixture therefore compares only a source-grounded synthetic case:

- CNY 100,000 NAV;
- 0.95 exposure;
- one target;
- CNY 10.00 price;
- zero current shares;
- 100-share lot;
- CNY 95,000 target;
- 9,500-share BUY intent.

Comparable layers are `00_CASE_INPUT`, `03_DECISION_BUDGETING`, and `04_ORDER_INTENT`. The remaining seven layers are `NOT_COMPARABLE_LEGACY_SCOPE`. Comparable layers use `copy_with_parity` and must return pair verdict `MATCH`; the aggregate report remains `NOT_COMPARABLE_LEGACY_SCOPE`, with Calendar/Session as the first uncovered layer. This is scope evidence, not economic parity.

Immutable source identity:

- archive SHA-256 `1fea4f5a4ec8ab12ddb25c6c5bb525f91f8bac9e887f3e5b382b641a948c91c3`;
- content-tree SHA-256 `65f9812bd86241ac5fcfdfcca1cb8c28868edbdf007d747ecee8cc68ee20d089`.

## Frozen evidence

The exact field order, type literals, manifest rows, fixed digests, limitations, failure precedence, inherited hashes, Journey controls, parity coverage and byte hashes are frozen by:

- `tests/fixtures/runtime/profiles/cn-a-share-resolved-profile-composition-v1.json`;
- `tests/fixtures/runtime/engine/cn-a-share-resolved-profile-development-journey-v1.json`;
- `tests/parity/contracts/cn-a-share-g08h-legacy-to-g08h-v1.json`;
- `tests/parity/fixtures/cn-a-share-g08h-v1/`;
- G08H contract, golden, Journey, parity, architecture and additive adversarial tests.

## Acceptance evidence

- focused G08H acceptance: `304 passed`;
- full repository: `1568 passed`;
- import boundaries: `96 files passed`;
- production and isolated support/parity mypy surfaces: clean;
- parity aggregate verdict: `NOT_COMPARABLE_LEGACY_SCOPE` with canonical report hash `sha256:d72471cc2ee87d2e414c04d92be9d7de94f1cf2fbe83aa422b27f610a79b7874`;
- primary LSP, pi-lens, `uv lock --check`, `git diff --check`: clean;
- final independent production and integration reviews: `NONE`.

The Payment artifact remains at phase 110 and Listing artifact at phase 120. Because the frozen G08G entries share one `recorded_at` and canonical Journal tie-break orders share ID 7 before cash ID 8, the development dispatcher publishes the payment artifact at its boundary and appends the exact immutable share/cash Journal batch at Listing; it does not mutate Engine state or create another accounting authority.

Real provider/archive qualification remains blocked on G12L/G12M.
