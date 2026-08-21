# Bounded negative searches

These searches locate first-party Binance material only. “No result” means no responsive authority was found in the listed search/extracted surface; it does not mean Binance has no such material anywhere.

## Search set A — endpoint schema and revision identity

Queries:

- `site:developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History fundingTime markPrice correction revision`
- `site:developers.binance.com "funding rate history" checksum revision id`
- endpoint extraction exact terms: `revision`, `checksum`, `corrected`, `supersedes`, `version`, `asOf`

Result:

- Found the official Funding Rate History endpoint reference.
- Extracted response fields were `symbol`, `fundingRate`, `fundingTime`, `markPrice`, and current `rateType`.
- No exact settlement-visible row revision identity, predecessor, correction timestamp, provider publication timestamp, immutable checksum, or as-of selector was found.

## Search set B — change-log correction policy

Queries:

- `site:developers.binance.com/en/docs/products/derivatives-trading-usds-futures/change-log funding`
- `site:developers.binance.com/docs/derivatives/usds-margined-futures/Change-Log correction revision funding`
- extracted English change-log exact terms: `fundingRate`, `rateType`, `correction`, `revision`, `checksum`

Result:

- Found dated endpoint additions/changes in 2019, 2023, and a later current entry.
- No match for `correction`, `revision`, or `checksum` in the extracted English change-log content.
- No target-effective settled-row correction policy was found.

## Search set C — Binance support funding semantics

Queries:

- `site:binance.com/en/support/faq USD-M funding rate settlement correction revised historical`
- `site:binance.com/en/support/faq "Funding Rate" "settlement" "USDⓈ-M"`

Result:

- Found Binance funding-rate and mark-price FAQs.
- The funding FAQ points to historical funding rates but did not provide revision identity, correction lineage, or a permanent-finality guarantee in the reviewed extraction.
- Current FAQ content reports a post-target update, so it was not used as target-effective 2024 revision authority.

## Access limitations

Direct raw fetches to Binance developer docs, the public API, and official GitHub raw content were rejected because the runtime resolved them into `198.18.0.0/15` and the fetcher blocked that range under its SSRF policy. No authenticated workaround, cookie, credential, or relaxed security configuration was used.
