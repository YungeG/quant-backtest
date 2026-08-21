# Closed limitation set — G12M-BHA-01B

This set is closed for BHA-02 consumption. Adding, weakening, or reclassifying an item requires new first-party evidence and a new version.

| ID | Class | Closed statement | BHA-02 consequence |
| --- | --- | --- | --- |
| BHA01B-B1 | **CAUSAL BLOCKER** | The documented Funding Rate History row has no exact revision identity, predecessor, or provider publication timestamp binding the value visible at settlement. | Fail closed: current row cannot establish the exact settlement-visible revision. |
| BHA01B-B2 | **CAUSAL BLOCKER** | The documented endpoint has no as-of/revision selector; a value fetched later cannot be distinguished as original versus later corrected. | Do not backdate the current response or infer equality with the settlement-visible value. |
| BHA01B-L1 | ADR 0008 limitation | No permanent finality or immutable provider checksum guarantee was found on the bounded surfaces. | This item alone may remain an explicit provider-finality limitation; it cannot waive B1/B2. |
| BHA01B-L2 | Scope limitation | Negative findings cover only the enumerated first-party endpoint reference, USDⓈ-M change log, Binance funding FAQ, listed queries, and exact terms. | No provider-global completeness or “never corrected” claim. |
| BHA01B-L3 | Effective-date limitation | Current endpoint documentation includes schema added after 2024; no archived target-period revision-policy bytes were retained. | Only the dated 2023-11-01 `markPrice` change is treated as predating the target rows; current schema is not wholly target-effective. |
| BHA01B-L4 | Evidence acceptance limitation | Direct raw bytes were blocked; no upstream SHA-256 replay or canonical SourceSnapshot was produced in this runtime. | Independent raw capture/hash review is still required, but successful capture would not by itself cure B1/B2 absent new authority. |
| BHA01B-L5 | Grade/governance limitation | Source-bounded research cannot mint or upgrade ResultGrade, and later corrections cannot silently alter prior Runs. | Preserve `UNKNOWN`; qualification remains fail-closed. |

## Conclusion

`UNKNOWN_CAUSAL_BLOCKER`

Missing permanent finality is retainable as a limitation. Missing identity for the exact revision visible at settlement is causal blocking and is not eligible for downgrade.
