# G08H Profile Composition and Parity Readiness Audit

## Verdict

G08H remains **DRAFT / BLOCKED**. G08A–G08G are `PASSED`, so the component implementations exist, but the composition contract, typed scope/revision evidence, Runtime dispatcher plan, fixture identity, and parity contract are not frozen.

This is a readiness blocker record, not an implementation specification and not a real-market qualification claim.

## Correct ownership boundary

G08H combines three existing seams:

- production pure composition in `backtest-runtime`, analogous to G10G;
- development-only dispatcher and Journey assembly in `tests/support`, reusing the G09H profile-neutral financial-dispatch seam without adding an A-share branch to generic Engine/Runner/Timeline/Ledger code;
- parity plan/tooling in `tools/parity` and `tests/parity`.

G08A–G08G remain owned by `trading-kernel profiles/cn_a_share`; G08H must consume them rather than create replacement Calendar, Settlement, Order Rule, Fee/Tax, Entitlement, Accounting, Journal, Ledger, Registry, or execution authorities.

## Existing repository authorities

The repository already has:

1. G08A Calendar/Session, G08B T+1 Settlement, G08C Quantity Lattice, G08D historical Order Rules/Price Limits, G08E Fee/Tax, G08F Corporate Action Entitlement, and G08G Corporate Action Accounting;
2. generic `MarketSemanticsProfileRegistration`, `SimulationProfileRegistration`, `ExecutionAccountProfileRegistration`, `BacktestProfileRegistry`, and the G09H profile-neutral `FinancialDispatcherSpec`/`FinancialDispatchPlan`/`ScheduledAccountEvent` plus Journal/Ledger replay, Timeline and Runner seams;
3. the G10G production-composer plus development-dispatcher pattern;
4. the G10H layered parity pattern, including explicit `NOT_COMPARABLE_*` verdicts;
5. authoritative Journal-prefix and Ledger replay identities needed to prove that Settlement consumes already-booked Fill accounting.

## Missing typed declarations before READY

### 1. Instrument and execution-scope qualification

Current `InstrumentDefinition` values prove broad Equity type, Venue and currencies, but cannot prove all caller preconditions deferred by G08B–G08F. G08H needs one frozen immutable declaration/evidence schema for the development fixture that explicitly binds, rather than infers:

- ordinary domestic CNY A-share;
- standard cash auction;
- XSHG or XSHE venue;
- not B/H share, ETF, REIT, Stock Connect, block trade or after-hours mechanism;
- no lending/repo, pledge/freeze, restricted/pre-IPO or differential-distribution scope.

This evidence must remain development-grade and must not claim provider completeness or real-market qualification.

### 2. Account-scope qualification

Existing generic account/risk values can express long-only and cash-funded behavior, but the exact G08H declaration and consistency checks are not frozen. The contract must explicitly bind cash account, domestic access, no margin/short, no Stock Connect, no available-margin authorization, account identity and Venue identity.

### 3. Corporate Action revision-set closure

G08F proves only the supplied Candidate/Snapshot values. G08H still needs immutable caller-supplied closure evidence for:

- the complete closed announcement revision set;
- the complete closed register revision set;
- terminal revision/cancellation state;
- source snapshot/manifest identity and coverage;
- captured-at/available-at causality;
- cross-query stable-ID conflict detection for corporate-action, snapshot, register-series and revision identities.

No current A-share schema binds a caller declaration that a supplied revision set is closed. G08H must freeze that schema before a composer can validate the supplied set/chain, source snapshot, coverage, availability and terminal state. The pure composer cannot prove that an external provider/archive omitted nothing; that real-source completeness remains G12L/G12M scope.

## Corporate Action tax boundary

G08G does **not** apply `APPLIED` or `DEFERRED_UNSUPPORTED` actions. Both cash and share translators return `UNSUPPORTED_TAX_DISPOSITION` unless the evidence is exactly `NOT_APPLICABLE`. Therefore G08H v1 does not need to invent a deferred-tax Lot flag or later-transfer state machine.

The G08H development composition must preserve the existing `NOT_APPLICABLE`-only scope and fail closed before any Journal/Lot effect for other dispositions. A future Gate that supports deferred taxation would require a separately frozen taxable-transfer authority.

## Component composition gap

No `equity.cn_a_share.v1` resolved profile currently exists. G08H has not frozen:

- production request/result/failure/outcome/composer names and canonical schemas;
- the exact 12-slot `ProfilePortType` manifest;
- which existing generic no-financing/no-margin/no-liquidation/CNY-valuation components are reused and how their digests are bound;
- Market, Simulation and Execution Account keys/versions/capabilities;
- profile limitations and exact grade flags;
- failure-code declaration and first-failure precedence.

The missing explicit A-share component classes are not themselves a reason to create new engines. Existing versioned generic/no-op components may be reused if the final manifest and digests are frozen exactly.

## Runtime lifecycle gap

Generic scheduled-event machinery exists, but no development A-share dispatcher or execution-case builder currently:

- maps frozen payment/listing operation keys to the G08G translators;
- supplies the exact request payloads and Timeline events at phases 110/120;
- appends/replays the resulting Journal entries through the existing dispatcher authority;
- proves full/prefix/resume reconstruction in an Engine Journey;
- preserves G08G failure outcomes atomically without partial effects.

This belongs in development test support; generic Runtime code must not import or branch on `CnAShare*` types.

## Parity reality

The immutable `cycle-rotation-platform` source is mapped as `reimplement_with_reference` with `comparator_contract: null`. It has no authoritative Calendar/Session, true T+1 Settlement, historical Price Limit, exact Fee/Tax, Corporate Action lifecycle, or Journal/Ledger accounting oracle.

Consequently G08H cannot claim exact legacy equivalence for those layers. Before READY it must freeze one of these two policies:

1. a G10H-style layered report whose unsupported legacy layers are explicitly `NOT_COMPARABLE_LEGACY_SCOPE`, with any comparable legacy budgeting/order/final-result layers defined exactly; or
2. a different immutable source artifact that is a real oracle for the claimed layers.

A `NOT_COMPARABLE` report is evidence of scope, not evidence of economic parity. The exact layer set, projections, verdict rules, first-divergence behavior and fixture IDs are still missing.

## Explicit retained exclusions

- XSHG bonus/capitalization remains unsupported; G08F/G08G already fail closed. G08H must retain that limitation unless separate provenance is frozen.
- Real provider/archive completeness, live security classification and deployment qualification remain G12L/G12M concerns.
- G08H output remains `grade=development`, `decision_grade_eligible=false`, `profile_qualified=false`, and `deployment_authorized=false`.

## Exact prerequisites for DRAFT → READY

1. Choose and freeze the development-only scope and parity policy above.
2. Freeze the production module path, exact public names, schemas, canonical hashes and exports.
3. Freeze instrument/account scope evidence and Corporate Action revision-closure evidence.
4. Freeze the profile manifest, capabilities, dispatcher spec/operation keys, failure precedence and reconstruction invariants.
5. Freeze static fixture IDs, exact test commands, expected artifacts and parity layers/verdicts.
6. Add RED contract/golden/Journey/parity/boundary tests and obtain an independent dry review.

Until all six are complete, implementation must not begin and the Gate remains `DRAFT / BLOCKED`.
