# G12L Binance USDⓈ-M Funding History Evidence v1

## Decision status

`G12L-BINANCE-USDM-FUNDING-HISTORY-V1` is `DRAFT / BLOCKED`. A finite,
unauthenticated official Funding Rate History response proves that Binance can
supply the exact G10E fields, including funding-time mark price. It does not
provide a provider checksum, immutable publication revision, or correction
closure, so it is development evidence rather than an accepted G12L source.

## Exact request

```text
GET https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&startTime=1704067200000&endTime=1704153599999&limit=100
```

The exact response was fetched twice and had identical bytes:

```text
response_sha256: e9f73f9c845c28abb31037d8230df2d6f13d5d368c43436e891fcc757372c338
byte_count: 379
record_count: 3
```

Each record contains exactly `symbol`, `fundingTime`, `fundingRate`, `markPrice`,
and `rateType`. The three funding times are 2024-01-01 00:00, 08:00, and 16:00
UTC. Rates and mark prices are non-empty ordinary decimal strings and
`rateType` is `Regular`. These fields map directly to the existing G10E
`BinanceUsdmFundingRateRecord`; no nearby kline or manufactured funding mark is
needed.

Primary source:

- <https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History>

## Exact G12A capture

```text
acquired_at_epoch_nanoseconds: 1786934053390511612
snapshot_id: sha256:0d4566742f51b18d66a28605c087ec3604769ab04e6fc551d71c9b32033b69a9
content_tree_hash: sha256:a55fd58ce7f37e829b37c1a6fb94c1426a79c0b97aa0df3c6e793273506b4680
provenance_hash: sha256:18a2286003de03ae71aa343a83b75432653ed0e1b490dcf5f3608b37896aa058
```

## Blocking conclusion

The capture is sufficient for offline development and G10E contract fixtures,
but not for G12L acceptance:

1. the response has no adjacent provider checksum or signed content identity;
2. the endpoint is a current query, not an immutable historical publication;
3. Binance documents no revision/correction/supersession terminal set for it;
4. the only defensible availability is the later G12A acquisition time;
5. therefore it cannot qualify 2024 intraday replay, G12I, G12M, decision-grade,
   live, or deployment authority.

The next acceptable upgrade requires an immutable first-party funding-history
publication carrying both rate and mark price, or provider revision evidence
that closes corrections for this exact finite response.
