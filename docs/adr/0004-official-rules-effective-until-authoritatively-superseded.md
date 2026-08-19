# ADR 0004: Official Rules Are Effective Until Authoritatively Superseded

- Status: Accepted
- Date: 2026-08-19
- Scope: G12H

## Context

The frozen G08E fee/tax RuleBooks use finite half-open Bands and fail closed outside them. G12H correctly proved that those August-2023 Bands do not cover the preserved July-2026 target. Official rules, however, commonly state an effective start without a legal sunset. Treating that missing sunset as either a finite gap or eternal validity conflates source-law continuity, evidence availability, and finite execution coverage.

## Decision

For a precisely scoped official rule revision, economic effect begins at its authoritative effective time and continues until a competent authority makes an authoritative successor effective. Amendment, correction, replacement, repeal, suspension, invalidation, or another scope-changing official act may be a successor; an equal number, third-party statement, current page alone, or unsuccessful search is not.

Source authority remains distinct from execution authority:

- successor closure identifies the official revision chain and terminal state as of an explicit official-record cutoff;
- a target-scoped projection clips that closed source authority to one finite target;
- execution continues to consume existing finite RuleBook/Band types and fails closed outside the projection;
- RuleBook identity binds execution economics, while closure and projection identities separately bind provenance, cutoff, target, and derivation.

Availability is never backdated. An as-of closure describes the authoritative record visible at its cutoff. A retrospective closure uses evidence available after the target to establish the target history as of a later cutoff; it produces a new additive artifact and publication, while the historical composition instant remains unchanged. Later corrections or successors produce another version and never rewrite prior PASSED bytes.

The G12H analyzer may proceed only after exact predecessor, post-target endpoint, competent-authority successor-index, candidate-disposition, and closure evidence passes. Acquisition controls such as exact bytes, receipts, headers, redirects, rendered captures, and pagination termination are sufficient proof methods; they become mandatory contract fields only where the selected closure evidence requires them.

## Consequences

- Existing G08E/G08H types, fixtures, hashes, and G12C/D v1 publication remain byte-identical.
- No open-ended interval or fallback is added to Runtime execution.
- No Runtime/profile composer or source projector is authorized before real closure evidence passes.
- If projection code is needed after closure, it is one concrete pure seam beside the existing Kernel A-share fee/tax types; Builder publication imports neither Kernel nor Runtime.
- A new additive v2 five-dimension declaration/publication must retain false provider, decision-grade, live, and deployment qualification unless independently proven.
- The current G12H result remains `COVERAGE_GAP / market_fees` until the additive evidence and publication pass.
