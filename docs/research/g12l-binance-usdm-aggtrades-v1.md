# G12L Binance USDⓈ-M Daily Aggregate-Trades Evidence v1

## Decision status

`G12L-BINANCE-USDM-AGGTRADES-V1` is the second concrete provider slice and is
`DRAFT / IN PROGRESS`. It selects Binance Public Data USD-M daily `aggTrades`,
`BTCUSDT`, UTC date `2020-01-01`. This note freezes real source bytes and exact
G12A identity only; normalization and acceptance remain.

## First-party authority

Binance's public-data repository states that USD-M futures aggregate-trade files
come from `/fapi/v1/aggTrades`, are available as daily/monthly archives, and have
adjacent checksum files. The accepted G10D source-semantics research freezes the
provider fields and maps aggregate-trade price at transaction time only to
`PricePurpose.EXECUTION_REFERENCE`.

Sources:

- <https://github.com/binance/binance-public-data/blob/5c7f3197/README.md>
- <https://github.com/binance/binance-public-data/blob/5c7f3197/python/README.md>
- <https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Aggregate-Trade-Streams>
- `docs/research/binance-usdm-price-purpose-streams-primary-sources.md`

## Exact finite scope

```text
archive: https://data.binance.vision/data/futures/um/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2020-01-01.zip
checksum: https://data.binance.vision/data/futures/um/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2020-01-01.zip.CHECKSUM
```

| Member | SHA-256 |
| --- | --- |
| ZIP | `638e72c179e4965c2a6521bb27295930d09126433efe0cc3acd4e925ada955ac` |
| CHECKSUM | `54f9a3ec8d0ea0363fcd730c2eb43399fa425d2d1fd803a7261f761af78d8499` |
| CSV | `b296db90ad4f8a20cd888cb7ce4a4199409ed14ad488331fe1a6b4943e6a53c0` |

The ZIP contains exactly one headerless CSV with 71,359 seven-field rows. Frozen
field order is aggregate-trade ID, price, quantity, first trade ID, last trade
ID, transaction time milliseconds, and buyer-maker flag. Aggregate-trade IDs
exact-cover `18374167..18445525`; transaction times are nondecreasing and remain
inside `2020-01-01` UTC. Price scale is at most 2 and quantity scale at most 3.
This proves internal fixture sequence closure, not exchange outage completeness.

## Exact G12A identity

```text
acquired_at_epoch_nanoseconds: 1786925819571748917
snapshot_id: sha256:84e362ddf3a1a7567c436160bb4bb6102324cd20474a4c2c2b0a38b388142c65
content_tree_hash: sha256:3e51e591737b5928ce796dc555b266b7d49d48e88b1051fbb9c6aa0b957993d7
provenance_hash: sha256:70908485e1e1baddf684248282fce1ba78dd5df4f066ccc3cf714ec892bac5d7
```

The conservative availability authority is the later G12A archive acquisition
time, never transaction time plus invented latency. The future normalizer must
emit only an EXECUTION_REFERENCE stream, preserve trade IDs/timestamps/decimal
strings and buyer-maker evidence, reject replacement/provenance mutation, remain
o-network/off-root, and keep G12I/G12M and deployment flags false.
