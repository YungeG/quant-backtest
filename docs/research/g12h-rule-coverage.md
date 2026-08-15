# G12H Rule Coverage Readiness Analysis

## Decision status

G12H remains **DRAFT / BLOCKED**. G12C is PASSED, but the repository does not yet expose a Builder-consumable authority that maps one market profile to its required historical rule dimensions and exact typed rule-source projections.

This note records the blocker; it does not authorize implementation, Runtime integration, decision-grade use, or deployment.

## Verified existing authority

- `MarketSemanticsProfileRegistration` lives in Backtest Runtime and binds profile identity, required Bundle capabilities, and a complete `ProfileComponentRef` manifest.
- It does **not** expose `required_rule_dimensions()` or another historical-rule coverage declaration.
- Existing G08/G10 rule books and resolvers live in Trading Kernel and own economic rule behavior.
- Builder may not import Backtest Runtime or Trading Kernel production code.
- G12C validates Bundle/Event structure and identity, but it does not describe which rule dimensions a profile requires or how typed historical rule intervals are represented.

Therefore G12H cannot infer required dimensions from `ProfilePortType`, enumerate Kernel rule books, or create a generic rule registry without inventing a second authority.

## Missing prerequisite contract

Implementation requires one preceding immutable declaration owned by profile/build evidence and consumable from Builder without Runtime/Kernel imports. It must bind:

- profile key, version, digest, and component-manifest hash;
- canonical required rule-dimension keys;
- for each dimension, the exact normalized source schema/version and source identity expected in the Bundle;
- exact half-open Bundle coverage target;
- explicit zero-required-dimension semantics when applicable;
- declaration hash and immutable artifact/source authority;
- fixed `decision_grade_eligible=false` and `deployment_authorized=false`.

The declaration may project existing typed Kernel rule sources, but the projection shape and mapping parity must be frozen before G12H. G12H must not define that mapping opportunistically inside its validator.

## Provisional downstream outcome

Once the prerequisite exists, G12H may own one pure Builder validator returning atomic XOR:

- `RuleCoverageReport`, or
- `RuleCoverageFailure`.

The report should bind the G12C Bundle ref, profile/declaration identity, one exact entry per declared required dimension, interval/source hashes, complete half-open coverage, unique resolution evidence, and false qualification flags.

A likely failure order is:

1. `invalid_input`;
2. `bundle_declaration_mismatch`;
3. `missing_required_dimension`;
4. `coverage_gap`;
5. `coverage_overlap`;
6. `source_identity_mismatch`.

These names remain provisional until the prerequisite declaration and normalized rule-source schemas are frozen.

## Evidence needed to become READY

- an immutable profile-to-rule-dimension declaration with real fixture evidence;
- at least one exact normalized historical rule-source schema tied to G12C Events;
- test-only parity from that projection to the authoritative typed Kernel rule book;
- explicit empty-dimension behavior;
- import-boundary proof that Builder does not import Runtime/Kernel;
- a RED matrix for gaps, overlaps, missing dimensions, identity mismatch, precedence, repeat hashes, and atomic failure.

## Non-goals

- No generic Rule superclass, registry, DSL, evaluator, callback, or second economic engine.
- No inference from profile component ports to historical rule dimensions.
- No current/live-rule fallback, latest-wins behavior, interpolation, or warning-only mode.
- No provider completeness claim; G12L owns source authority.
- No Runtime boot branch or market qualification; G12M owns final qualification.
