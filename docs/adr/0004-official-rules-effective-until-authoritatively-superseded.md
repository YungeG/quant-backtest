# ADR 0004: Official Rules Are Effective Until Authoritatively Superseded

- Status: Accepted
- Date: 2026-08-19
- Scope: G12H

## Context

The frozen G08E fee/tax RuleBooks use finite half-open Bands and fail closed outside them. G12H correctly proved that those August-2023 Bands do not cover the preserved July-2026 target. Official rules, however, commonly state an effective start without a legal sunset. Treating that missing sunset as either a finite gap or eternal validity conflates source-law continuity, evidence availability, and finite execution coverage.

## Decision

For a precisely scoped official rule revision, economic effect begins at its authoritative effective time and continues until a competent authority makes an authoritative successor effective. Amendment, replacement, repeal, suspension, invalidation, or another scope-changing official act may be an economic successor; an equal number, third-party statement, current page alone, or unsuccessful search is not.

Documentary correction and economic succession are separate lineages. A corrected publication names the prior representation through `corrects_revision_id`; an economic state names its economic predecessor through `economic_predecessor_revision_id`. At the official-record cutoff, closure first selects the terminal documentary representation of each official act, then orders those selected economic states by authoritative `effective_from`. A retroactive correction is not rejected merely because it was published later or moves an effective boundary backward. Unresolved documentary/economic forks, gaps, overlaps, or conflicts fail closed.

Every economic state binds the exact calculation basis and applicability scope: Venue, board, instrument class, currency, and mechanism. Projection is forbidden when that basis or scope cannot be represented and enforced by the existing execution policy; Main-Board-only evidence cannot produce a Venue-wide RuleBook.

Source authority remains distinct from execution authority:

- successor closure identifies the selected documentary representations and economic state chain as of an explicit official-record cutoff;
- a target-scoped projection clips that closed source authority to one finite target;
- execution continues to consume existing finite RuleBook/Band types and fails closed outside the projection;
- RuleBook identity binds canonical target economics, while closure and projection identities separately bind evidence, provenance, cutoff, target, scope, basis, and derivation.

Availability is never backdated. Every retrospective closure satisfies `target_to_exclusive <= official_record_as_of <= closure_evidence_available_at`. Selected official revisions must be published or recorded by `official_record_as_of`; captures and receipts must be available by `closure_evidence_available_at`. The old time is named only `historical_profile_composed_at` and is never substituted for either cutoff. Violations fail as `CUTOFF_INVALID`.

Any new evidence creates new closure, projection, declaration, and publication identities. Existing finite RuleBook bytes and hashes change only when canonical target economics change. Later corrections or successors never rewrite prior PASSED bytes.

The G12H analyzer may proceed only after exact predecessor, post-target endpoint, competent-authority successor-index, candidate-disposition, and closure evidence passes. Acquisition controls such as exact bytes, receipts, headers, redirects, rendered captures, and pagination termination are sufficient proof methods; they become mandatory contract fields only where the selected closure evidence requires them.

## Consequences

- Existing G08E/G08H types, fixtures, hashes, and G12C/D v1 publication remain byte-identical.
- Closure-only evidence changes leave finite execution RuleBook bytes unchanged; target-affecting economic changes produce new RuleBook hashes.
- No open-ended interval or fallback is added to Runtime execution.
- No Runtime/profile composer or source projector is authorized before real closure evidence passes.
- If projection code is needed after closure, it is one concrete pure seam beside the existing Kernel A-share fee/tax types; Builder publication imports neither Kernel nor Runtime.
- A new additive v2 five-dimension declaration/publication must retain false provider, decision-grade, live, and deployment qualification unless independently proven.
- The current G12H result remains `COVERAGE_GAP / market_fees` until the additive evidence and publication pass.
