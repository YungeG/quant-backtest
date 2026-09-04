# Closed limitation set — G12M-BHA-01B

This set is closed for BHA-02 consumption. Adding, weakening, or reclassifying an
item requires new first-party evidence and a new version.

| ID | Class | Closed statement | BHA-02 consequence |
| --- | --- | --- | --- |
| BHA01B-B1 | **CAUSAL BLOCKER** | No accepted first-party surface identifies the exact row revision, predecessor, or provider publication time for the value visible at settlement. | Fail closed: later current-state bytes cannot establish the exact settlement-visible revision. |
| BHA01B-B2 | **CAUSAL BLOCKER** | The accepted endpoint interface has no named as-of/revision selector and the accepted response shapes have no named revision lineage; original versus later-corrected value is indistinguishable. | Do not backdate a later response or infer equality with the settlement-visible value. |
| BHA01B-L1 | ADR 0008 limitation | No permanent-finality or immutable provider row-checksum guarantee is established by the accepted raw set. | This alone may remain an explicit provider-finality limitation; it cannot waive B1/B2. |
| BHA01B-L2 | Scope limitation | Negative findings cover only the enumerated pinned official GitHub files, exact public testnet response, and secondary bounded searches. | No provider-global completeness or “never corrected” claim. |
| BHA01B-L3 | Effective-date limitation | The 2022 connector establishes target-preceding request shape, but no accepted production response or revision-policy bytes come from the 2024 settlement period; a current response field is dated 2026. | Do not treat the current response schema or testnet rows as wholly target-effective for 2024. |
| BHA01B-L4 | Network/source limitation | Production developer docs and production `fapi` failed before HTTP response through this runtime's `198.18.0.0/15` fake-IP path; accepted raw bytes are pinned official GitHub and public testnet surfaces. | Evidence handling is accepted, but production/settlement-time authority remains absent. |
| BHA01B-L5 | Grade/governance limitation | Source-bounded research cannot mint or upgrade ResultGrade, and later corrections cannot silently alter prior Runs. | Preserve `UNKNOWN`; qualification remains fail-closed. |

## Conclusion

`UNKNOWN_CAUSAL_BLOCKER`

Raw-byte, receipt, hash, upstream replay, SourceSnapshot, and independent
primary-source review requirements are now satisfied. They repair the evidence
acceptance blocker but do not supply the missing settlement-visible revision
identity or permanent finality authority.
