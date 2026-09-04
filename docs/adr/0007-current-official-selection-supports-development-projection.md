# ADR 0007: Current Official Selection Supports Development Projection

- Status: Accepted
- Date: 2026-08-20
- Scope: G12H

For the finite July-2026 XSHE `DOMESTIC + ORDINARY_A_SHARE` target only, an issuer-owned current-document selector, current publication page, or current clean document captured after target end may support an additive development RuleBook projection even when it exposes no explicit status field and no complete successor/correction corpus. The evidence must bind exact official bytes, URL, headers, receipt time, hash, scope, basis, applicability, and economics; known candidates must be dispositioned, conflicts still fail closed, and the projection is clipped to the finite target.

This is a development assumption, not official historical closure. It does not set `official_record_as_of`, complete ADR 0004 successor closure, or authorize decision-grade, live, or deployment use. Artifacts use `development_evidence_available_at` and component-specific `observed_at` times, keep all authority qualifications false except explicit development projection authorization, and remain additive and immutable. Issuer-authenticated status/history evidence is still required before stronger qualification.
