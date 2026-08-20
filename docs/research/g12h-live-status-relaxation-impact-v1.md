# G12H live-status receipt-time relaxation impact v1

## Decision

ADR 0006 accepts the explicit governance alternative chosen after the competent status-register discovery: a verified receipt time may stand in for a missing source-declared record-state/as-of timestamp when an issuer-owned official live-status API response returns a nonblank status for the exact official act.

The exception is narrow. It does not accept a current page, blank status, search absence, category absence, or retrieval time without a qualifying explicit status API response. It also does not waive exact economic identity, corpus fit, successor/correction candidate completeness, or deterministic disposition requirements.

## Reassessment of captured evidence

Target end: `2026-07-30T16:00:00Z`.

| Lineage | Effect of ADR 0006 | Result |
|---|---|---|
| `exchange_handling` | None. The captured January 2026 SZSE fee table has no explicit live-status API result, and the captured business-rule/repeal registers do not declare fee-table corpus coverage. | `INSUFFICIENT` |
| `securities_regulatory` | None. The captured NDRC/MOF acts and SZSE collection representation have no explicit exact-lineage live-status API result and no complete post-target amendment/repeal/correction/successor channel. | `INSUFFICIENT` |
| `chinaclear_transfer` | None. ChinaClear's explicit repealed-business-rule registers are a different corpus from the fee-standard tables and expose no exact fee-table live-status API result. | `INSUFFICIENT` |
| `hkscc_transfer` | None. Specific 2025 amendments and the prospective November 2026 USM successor are dispositionable, but no official live-status API response explicitly declares the current clean Definitions/§21 identity or completeness of all amendment/correction/replacement channels. | `INSUFFICIENT` |
| `stamp_duty` | Partial. The NPC API's exact Stamp Duty Law result (`sxx=3`, officially mapped to `有效`) now qualifies to use its verified receipt time as record-state time. STA's exact Announcement 2023 No. 39 result remains blank for status, abolition date, and revision type, so it does not qualify. | `INSUFFICIENT` |

## Frozen outcome

ADR 0006 removes only the NPC Stamp Duty Law timestamp blocker. It does not produce a common qualified `official_record_as_of` for the five required lineages, so F1 remains fail-closed and no closure artifact, RuleBook, F2 projection, F3 publication, analyzer work, or qualification is authorized.

The next positive evidence must be one of:

1. an issuer-owned official live-status API response for the exact remaining official act or fee table, plus a complete declared candidate channel for its economic lineage; or
2. an issuer-authenticated archive/status certificate declaring corpus-through time and complete predecessor, successor, amendment, repeal, and correction relations.

Captured authority remains the immutable Wave 1 and register-discovery evidence recorded by the parent Acceptance Matrix. No previously PASSED artifact or identity changes.
