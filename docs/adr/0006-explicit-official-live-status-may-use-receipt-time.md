# ADR 0006: Explicit Official Live Status May Use Receipt Time

- Status: Accepted
- Date: 2026-08-20
- Scope: G12H

An issuer-owned official live-status API response that identifies the exact official act and returns an explicit nonblank status such as effective, active, modified, repealed, or not-yet-effective may use the verified response receipt time as that API response's record-state time when it supplies no source-declared record-state/as-of timestamp. G12H may therefore choose a common `official_record_as_of` no later than the earliest relied-on live-status API receipt or source-declared register-through time, provided every relied-on record-state time is at or after the target end and all bytes, requests, headers, redirects, receipts, status-enum mappings, and hashes are preserved.

This relaxation replaces only the missing record-state/as-of timestamp. It does not turn page presence, blank or null status, search absence, category absence, retrieval time by itself, or a register for the wrong corpus into authority. Exact rule identity, economic scope, predecessor/successor/correction candidate completeness, deterministic dispositions, and conflict-free target coverage remain mandatory under ADR 0004. A qualifying API observation can establish status through its receipt time; it cannot silently establish another act's status, an unrepresented amendment, or a fee-table lineage absent from the API's declared corpus.
