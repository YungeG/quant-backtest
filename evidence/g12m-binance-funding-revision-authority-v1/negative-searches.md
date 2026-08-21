# Bounded negative searches and acquisition aids

These searches locate candidate first-party Binance material only. Search excerpts
are secondary acquisition aids, excluded from `source-snapshot.json`, and are not
the acceptance basis. “No result” means no responsive authority was found in the
listed search/extracted surface; it does not mean Binance has no such material.

## Search set A — endpoint schema and revision identity

Queries:

- `site:developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History fundingTime markPrice correction revision`
- `site:developers.binance.com "funding rate history" checksum revision id`
- endpoint extraction exact terms: `revision`, `checksum`, `corrected`,
  `supersedes`, `version`, `asOf`

Acquisition result:

- Located the official Funding Rate History endpoint reference.
- Prompted capture of the pinned official connector request interface and generated
  response models now used as the raw acceptance basis.
- The search extraction itself is not used to assert field absence.

## Search set B — change-log correction policy

Queries:

- `site:developers.binance.com/en/docs/products/derivatives-trading-usds-futures/change-log funding`
- `site:developers.binance.com/docs/derivatives/usds-margined-futures/Change-Log correction revision funding`
- extracted English change-log exact terms: `fundingRate`, `rateType`, `correction`,
  `revision`, `checksum`

Acquisition result:

- Located dated schema-change terminology.
- Prompted capture of the exact pinned official connector changelog that dates the
  `rateType` response addition to 2026-07-28.
- The search-extracted 2023 `markPrice` passage remains secondary and no accepted
  claim depends on it.

## Search set C — Binance support funding semantics

Queries:

- `site:binance.com/en/support/faq USD-M funding rate settlement correction revised historical`
- `site:binance.com/en/support/faq "Funding Rate" "settlement" "USDⓈ-M"`

Acquisition result:

- Located Binance funding-rate FAQ material but no raw stable target-period bytes.
- The retained FAQ excerpt is contextual only and supplies no accepted revision
  identity, correction lineage, or permanent-finality guarantee.

## Exact raw-source negative boundary

On the accepted raw surfaces:

- the pinned 2022 request interface names `symbol`, `startTime`, `endTime`, and
  `limit`, not a row-vintage selector;
- the pinned generated response models name business fields but no row revision
  lineage;
- the generated models permit additional properties, so no provider-global field
  absence is asserted;
- the pinned 2026 changelog demonstrates response-schema evolution, not settled-row
  correction semantics;
- the testnet response is current and non-production, not 2024 authority.

## Access limitations

Exact unauthenticated attempts to production developer docs and production `fapi`
failed before HTTP response after resolving to `198.18.0.0/15`. Exact scope, times,
resolved addresses, exit codes, and stderr are retained in
`receipts/network-fake-ip-limitations.json`. Pinned GitHub raw and public testnet
requests succeeded without credentials.
