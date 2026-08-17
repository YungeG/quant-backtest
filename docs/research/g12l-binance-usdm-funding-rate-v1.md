# G12L Binance USDⓈ-M Monthly Funding-Rate Evidence v1

## Decision status

`G12L-BINANCE-USDM-FUNDING-RATE-V1` is the third concrete provider slice and is
`DRAFT / READY FOR ACCEPTANCE`. It freezes real Binance USD-M monthly
`fundingRate`, exact G12A identity, rate-only normalization, and G12C/D evidence.

## First-party authority

Binance's public-data repository lists USD-M `fundingRate` as a monthly futures
data family with adjacent checksum files. Binance Funding Rate History defines
the funding timestamp and applied rate. The archive selected here contains the
rate and interval only; it does not contain the funding-time mark price required
by the existing G10E source resolution.

Sources:

- <https://github.com/binance/binance-public-data/blob/5c7f3197/README.md>
- <https://github.com/binance/binance-public-data/blob/5c7f3197/python/README.md>
- <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History>
- `docs/research/binance-usdm-price-purpose-streams-primary-sources.md`

## Exact finite scope

```text
archive: https://data.binance.vision/data/futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2020-01.zip
checksum: https://data.binance.vision/data/futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2020-01.zip.CHECKSUM
```

| Member | SHA-256 |
| --- | --- |
| ZIP | `7f81b2f3694d13779e7e896b69d60cd61e9444d7b9f9e90df761935e1c1b76e2` |
| CHECKSUM | `3274779c977a6d657722bac4cc9f965bb774c5ba38aad391eb47ef183ae46120` |
| CSV | `b566eea750ede01486360de242ce63a727ebbbc81fb46fcfdf2fb68188b48835` |

The ZIP contains one CSV with the exact header `calc_time`,
`funding_interval_hours`, `last_funding_rate` and 93 rows. Nominal slots cover
2020-01-01 00:00 through 2020-01-31 16:00 UTC every eight hours. Provider
`calc_time` may be zero, one, or two milliseconds after its nominal slot; that
jitter is retained rather than rounded away. One source rate uses scientific
notation (`8.4E-7`), which must be preserved as raw evidence while normalization
also provides an exact ordinary-decimal representation.

## Exact G12A identity

```text
acquired_at_epoch_nanoseconds: 1786932488331056046
snapshot_id: sha256:8a42a791c9471a20f734d88660b37b7e967b8eabb6007078e625b220add11ebd
content_tree_hash: sha256:d596329bda3338709134d3b02403fb38f4cfed555a1b40910f877b15fba6196e
provenance_hash: sha256:7abdd0a03f8e3b833595492707869700fd19c410a68cd74c1eb419759d3f6e73
```

Availability is the later G12A archive acquisition instant, never a fabricated
funding-time latency. The future normalizer may emit only funding-rate
publication evidence, must preserve raw provider values and exact slot jitter,
and must not manufacture a funding mark price. Consequently this slice alone
cannot satisfy G10E, G12I, G12M, decision-grade, live, or deployment authority.
