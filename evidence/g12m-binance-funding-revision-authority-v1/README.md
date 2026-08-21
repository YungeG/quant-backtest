# G12M Binance funding revision authority evidence

## Scope

Research-only evidence for BHA-01B: correction/revision semantics of settled Binance USDⓈ-M Funding Rate History rows, especially whether the exact revision visible at a 2024 settlement can be identified later.

## Retained source index

| ID | First-party source | Request / URL scope | Retained artifact | Raw official bytes | SHA-256 / SourceSnapshot |
| --- | --- | --- | --- | --- | --- |
| S1 | Binance Developer Docs — Get Funding Rate History | `GET /fapi/v1/fundingRate`; current request parameters and response schema | `excerpts/funding-rate-history-current.txt` | unavailable: direct fetch blocked; readable search extraction only | not produced; must not be treated as accepted SourceSnapshot |
| S2 | Binance Developer Docs — USDⓈ-M Futures Change Log | funding endpoint entries; dated 2019-10-14, 2023-11-01, and current later schema entry | `excerpts/usds-m-change-log.txt` | unavailable: direct fetch blocked; readable search extraction only | not produced; must not be treated as accepted SourceSnapshot |
| S3 | Binance Support — Introduction to Binance Futures Funding Rates | current FAQ passages concerning historical rates and page date/disclaimer | `excerpts/funding-rate-faq-current.txt` | unavailable: direct fetch blocked; readable search extraction only | not produced; must not be treated as accepted SourceSnapshot |

## URLs

- <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History>
- <https://developers.binance.com/en/docs/products/derivatives-trading-usds-futures/change-log>
- <https://www.binance.com/en/support/faq/detail/360033525031>

## Local receipt metadata

The available tooling did not expose a wall-clock receipt timestamp or HTTP headers. The following stable local search receipt identifiers are retained:

- `mt31fw7a0cmufb` — endpoint reference and Binance funding FAQ readable extraction.
- `mt31hf5ol2wgte` — USDⓈ-M change-log readable extraction and bounded term search.

Direct `fetch_content(mode=raw)` attempts failed before content receipt for:

- `developers.binance.com` → resolved fake-IP `198.18.3.250`, rejected by SSRF policy.
- `fapi.binance.com` → resolved fake-IP `198.18.1.87`, rejected by SSRF policy.
- `raw.githubusercontent.com` → resolved fake-IP `198.18.0.75`, rejected by SSRF policy.

No cookie, credential, authorization header, environment value, or authenticated profile was used or retained.

## Hash and replay status

`manifest.sha256` records parent-validated SHA-256 values for the retained local
research artifacts. These hashes prove only the bytes committed in this evidence
subtree; they are not upstream HTTP-body hashes or a canonical SourceSnapshot. The
excerpts are exact passages copied from readable search extraction results and are not
claimed as raw HTTP response bytes.

## Effective-date status

- S2's 2023-11-01 entry is dated before the target 2024 rows and says `markPrice` was added to `GET /fapi/v1/fundingRate`.
- S1 is current documentation; it includes `rateType`, which S2 dates after the target period, so S1 is not wholly target-effective for 2024.
- S3 reports a post-target update and is contextual only.

## Acceptance boundary

This subtree is limitation evidence, not accepted causal authority. It does not establish provider availability time, exact settlement-visible revision identity, correction history, or permanent finality.
