# Independent primary-source acceptance review

## Result

**ACCEPTED for BHA-01B's bounded limitation finding; not accepted as target-period row-vintage authority.**

The acceptance basis is the exact unauthenticated first-party byte set in
`source-snapshot.json`, independently cross-checked across two official Binance
GitHub repositories and the Binance Futures public testnet API. Search-provider
excerpts are acquisition aids only and are excluded from the SourceSnapshot.

## Claim-to-source review

| Claim | Independent first-party check | Result |
| --- | --- | --- |
| The endpoint request surface is `GET /fapi/v1/fundingRate` with `symbol`, `startTime`, `endTime`, and `limit`, not an as-of or revision selector. | Official `binance-futures-connector-python` file pinned at 2022 commit `d30576a6d8e6edb706c8b013eb11167b58e9c33a`, lines 242-263. | Accepted for the request shape present by 2022; no claim about undisclosed parameters or later internal systems. |
| First-party response shapes expose business fields rather than a revision ID, predecessor, corrected-at time, publication time, or row checksum. | Official generated response models pinned at 2025 commit `38996023660752a75acf7ebbc4f9a504e10e336f` and 2026 commit `e44cdc9e57c76154f08676764bb6f21fbdb49c4a`; independently, the exact testnet body contains `symbol`, `fundingTime`, `fundingRate`, and `markPrice`. | Accepted only for those exact dated/current surfaces. The model permits additional properties, so this is not a provider-global field-absence claim. |
| Current schema cannot be backdated wholesale to 2024. | The pinned 2025 model has four named properties; the pinned 2026 model adds `rateType`; the pinned 2026 changelog dates that response modification to 2026-07-28. | Accepted. This is schema-evolution evidence, not settled-row correction evidence. |
| The current value cannot prove equality with the exact value visible at settlement. | The accepted request surface has no vintage selector and the accepted response surfaces have no named row-revision identity. | Accepted as a capability limitation. It does not claim Binance actually corrected any settled row. |
| Binance guarantees permanent finality or an immutable row checksum. | No positive statement exists in the accepted raw set. | Not established. Only a bounded `none found` limitation is permitted. |

## Independence and replay

- GitHub raw responses were received with HTTP 200 and compared byte-for-byte with
  local `git show <commit>:<path>` output from the two official repositories.
- The API response was fetched separately, unauthenticated, from
  `testnet.binancefuture.com` with HTTP 200.
- Each raw member hash is declared in its receipt and reconstructed through the
  existing G12A `freeze_source_snapshot` / `verify_source_snapshot` contracts.
- Production `developers.binance.com` and `fapi.binance.com` requests still failed
  before HTTP response because this runtime resolves them to `198.18.0.0/15`; the
  exact attempts are retained in `receipts/network-fake-ip-limitations.json`.

## Residual boundary

No accepted raw member is an archived production response from the 2024 settlement
instant, and no accepted first-party statement supplies row correction lineage or
permanent finality. Therefore the accepted evidence repairs the evidence-handling
blocker but does not change `UNKNOWN_CAUSAL_BLOCKER`.
