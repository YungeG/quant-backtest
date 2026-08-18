# G12H Rule Coverage Readiness Analysis

## Decision status

G12H remains **DRAFT / BLOCKED**, but its source-publication prerequisite is now closed. `G12CD-CN-A-SHARE-DEVELOPMENT-RULE-AUTHORITIES-V1` PASSED at `832f53a74d3f74436ecae8672bd1c0dd3530c814`, losslessly binding the five G08H development authorities to one immutable G12C/D Bundle.

This note does not authorize the G12H validator, provider completeness, Runtime integration, decision-grade use, or deployment. The remaining work is to freeze G12H's own declaration/report/failure contract and RED matrix against that Bundle.

## Grounded prerequisite evidence

`CnAShareProfileCompositionRequest` injects exactly five finite authorities whose rules or session coverage vary over time:

1. `calendar` — `CnAShareFrozenCalendar`;
2. `order_rules` — `CnAShareOrderRuleBook`;
3. `market_fees` — `CnAShareMarketFeeRuleBook`;
4. `stamp_duty` — `CnAShareStampDutyRuleBook`;
5. `corporate_action_entitlements` — `CnAShareCorporateActionEntitlementRuleBook`.

The remaining G08H market components are static algorithms or accounting policies and do not establish additional historical rule dimensions. This exact five-item order is grounded by the composition request rather than inferred from `ProfilePortType`.

The G08 typed authorities also ground the evidence that a later normalized projection must preserve:

- Calendar: Venue, calendar identity, local-date half-open coverage, every frozen day, and `calendar_hash`.
- Order rules: Venue, board applicability, local-date half-open bounds, source key/hash, rule-book key/version/hash, and band hash. Board applicability cannot be discarded because bands for different boards legitimately share time intervals.
- Market fees: Venue, UTC half-open bounds, the distinct handling/regulatory/transfer source-ref tuples, rule-book key/version/hash, and band hash.
- Stamp duty: Venue, UTC half-open bounds, source refs, rule-book key/version/hash, and band hash.
- Corporate-action entitlements: Venue, UTC half-open bounds, the complete ordered official source-ref tuple, rule-book hash, and band hash.

A truthful declaration must bind the resolved G08H market profile key/version/digest, `canonical_sha256(component_manifest)`, the ordered five dimensions above, the exact G08H timeline target, normalized schema/source identities, explicit fail-closed empty semantics, source-manifest identity, fixed development-only qualification flags, and constructor-recomputed hashes.

## Closed prerequisite blockers

### 1. Exact G12C/D rule-event projection

The PASSED prerequisite now freezes five providerless development streams, exact event types/capability, revision and canonical-body identities, immutable G08H profile/manifest binding, target coverage, availability, and false qualification flags. Builder production code imports neither Runtime nor Trading Kernel.

### 2. Typed applicability remains lossless

The publication embeds each complete canonical G08 authority body rather than flattening it to interval/source-only rows:

- G08D order bands are selected by Venue **and board**, and use `date` bounds interpreted in the A-share local trading-date domain.
- G08E market-fee bands preserve three independently sourced fee classes; flattening them into one undifferentiated source tuple loses exact source identity.
- The frozen Calendar has no generic `source_ref`; its immutable identity is the calendar body/hash.

The fixed five-dimension declaration and complete canonical bodies preserve these applicability/evidence fields without adding a generic discriminator, payload DSL, or second rule model.

### 3. Coverage target and Bundle binding

The PASSED declaration binds the exact G08H profile request, market-profile digest, component-manifest hash, source-manifest hash, timeline target, availability instant, five intrinsic authority hashes, and five canonical body hashes to one exact G12C/D manifest/event set.

## Readiness verdict

The smallest grounded prerequisite is PASSED. G12H still remains **BLOCKED** because its analyzer contract is not frozen. The next readiness slice must define one exact Builder-owned declaration, atomic report/failure shapes, interval/applicability semantics, deterministic precedence, and RED fixtures against the accepted manifest/events.

No provider truth, generic rule model, Runtime boot path, public Builder root export, decision-grade claim, or deployment authority follows from the prerequisite publication.

## Provisional downstream outcome

Only after that source-contract freeze may G12H add one pure Builder validator returning atomic XOR:

- `RuleCoverageReport`, or
- `RuleCoverageFailure`.

The deterministic RED matrix remains:

1. `invalid_input`;
2. `bundle_declaration_mismatch`;
3. `missing_required_dimension`;
4. `coverage_gap`;
5. `coverage_overlap`;
6. `source_identity_mismatch`.

These names remain provisional until the prerequisite contract is frozen.

## Non-goals

- No generic Rule superclass, registry, resolver, DSL, evaluator, dispatcher, cache, or second economic engine.
- No inference from profile component ports to historical rule dimensions.
- No current/live-rule fallback, latest-wins behavior, interpolation, or warning-only mode.
- No provider completeness claim; G12L owns source authority.
- No Runtime boot branch or market qualification; G12M owns final qualification.
