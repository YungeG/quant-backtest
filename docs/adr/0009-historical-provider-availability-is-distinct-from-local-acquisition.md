# ADR 0009: Historical Provider Availability Is Distinct from Local Acquisition

- Status: Accepted
- Date: 2026-08-21
- Scope: G12M historical market-data qualification

## Context

Historical market facts are often acquired by this repository long after they became
effective. The local receipt proves when exact retained bytes were acquired, but it
does not by itself prove when the exact event revision was usable by a market
participant. Treating those times as equivalent either creates lookahead or blocks a
causal historical Run for the wrong reason.

The accepted Binance USD-M funding-history source-bounded v2 artifacts correctly
retain a conservative 2026 local receipt time. They are valid post-hoc evidence, but
they do not establish when the exact 2024 revisions were available under Binance
semantics.

## Decision

G12M keeps four times distinct:

- **Event Time** is when the market fact became effective.
- **Provider Availability Time** is the earliest defensible instant the exact event
  revision was usable under provider or market semantics.
- **Acquisition Time** is when this repository acquired the retained bytes.
- **Assessment Time** is when G12M evaluated already-published evidence and Run
  identities.

For causal market-data contracts, `available_time` means Provider Availability Time,
not repository download time. `observed_at` and SourceSnapshot acquisition time remain
exact local Acquisition Time evidence.

Dataset-specific provider semantics may establish Provider Availability Time only
when exact, target-effective authority is retained and hashed. Missing provider
availability authority is `UNKNOWN` and remains fail-closed and post-hoc-only. A
conservative source artifact may retain Acquisition Time as its visibility boundary,
but that does not convert the receipt into provider availability authority.

The accepted Binance funding-history v2 artifacts remain immutable and retain their
original meaning. Their `available_time` remains the 2026 local receipt instant; it is
not reinterpreted as 2024 provider availability. Any causal repair is additive and
uses new identities.

Each provider correction or revision has its own Provider Availability Time. Future
correction and finality uncertainty remains an explicit limitation under
[ADR 0008](0008-source-bounded-decision-grade.md) and cannot silently alter prior
Runs, source artifacts, or assessments.

Dataset-specific authority is permitted. A global availability framework, provider
registry, policy DSL, fallback chain, or new grade system is not. G12M governance and
source-bounded qualification never mint, derive, upgrade, or downgrade `ResultGrade`;
they only bind the grade established by Runtime Resolution and Integrity.

## Consequences

Accepted upstream evidence and causal Runtime qualification are separate states.
Exact post-hoc Binance v2 evidence remains accepted while causal Runtime
qualification remains blocked until target-effective provider availability authority
and the other existing Runtime prerequisites are independently accepted.

Unknown provider availability cannot be repaired by backdating to Event Time,
extending a Run to local Acquisition Time, or moving Assessment Time. Stronger
provider authority is additive and preserves every immutable v1/v2 artifact and prior
Run identity.
