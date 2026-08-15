# G12H Rule Coverage Readiness Analysis

## Decision status

G12H remains **DRAFT / BLOCKED**. The G08H composition request grounds the candidate historical-rule dimensions, but the repository still does not contain exact G12C rule-event authority from which a Builder-consumable normalized projection can be frozen without invention.

This note records the blocker; it does not authorize the G12H validator, Runtime integration, decision-grade use, or deployment.

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

## Remaining exact blockers

### 1. No authoritative G12C rule-event projection

G12C freezes generic `MarketEvent` and Bundle structure, but no PASSED fixture defines A-share rule stream keys, event types, capabilities, payload schemas, revision identities, or the mapping from the five typed G08 authorities into those events. Existing A-share support emits account financial events only. Choosing those missing values here would invent the source contract that G12H is meant to validate.

### 2. The proposed interval/source-only shape loses typed applicability

A normalized band containing only time bounds and source refs is not parity-complete:

- G08D order bands are selected by Venue **and board**, and use `date` bounds interpreted in the A-share local trading-date domain.
- G08E market-fee bands preserve three independently sourced fee classes; flattening them into one undifferentiated source tuple loses exact source identity.
- The frozen Calendar has no generic `source_ref`; its immutable identity is the calendar body/hash.

Without frozen applicability and evidence fields, valid parallel bands would appear as overlaps and source mismatches could be hidden. Adding a generic discriminator or payload DSL would be a new rule model and is not authorized.

### 3. Coverage-target and Bundle binding are not frozen together

The resolved G08H fixture has a finite `TimelineWindow`, while a G12C Bundle independently has manifest coverage. No PASSED artifact binds one exact G08H resolved-profile digest/component manifest and the five typed projections to one exact G12C Bundle manifest/event set. A declaration hash created before that binding would certify test-authored values rather than existing immutable source authority.

## Readiness verdict

The smallest grounded prerequisite is now identified, but it cannot yet be implemented exactly. G12H therefore remains **BLOCKED**. No production contract, static normalized fixture, parity mapper, RED validator tests, public export, or Builder code is added.

To become READY, a preceding source-contract freeze must provide one immutable A-share G12C rule Bundle whose five stream/event payload schemas are direct lossless projections of the G08 typed authorities, including applicability keys and source evidence. Test-only Kernel parity can then prove exact reconstruction without any production Builder import of Runtime or Trading Kernel.

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
