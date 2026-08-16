# G12 MarketBundle Builder Execution DAG

## Outcome

Turn caller-authorized source acquisition evidence into immutable, validated, publishable MarketBundles and market-specific decision-grade qualification without allowing Builder authority into Backtest Runtime.

## DAG

```text
G00 → G12A → G12B → G12C → G12D → G12E → G12F
                    ├──────→ G12H
                    ├─→ G12G → G12I
                    └──────→ G12K

G12A–K + provider evidence → G12L-* → G12M-*
real old artifact          → G12J
```

## Gates

| Gate | Outcome | Contract dependencies | Primary module/package |
| --- | --- | --- | --- |
| [G12A](g12a.md) | Deterministic SourceSnapshot | G00 | `market-bundle-builder/source_snapshots.py` |
| [G12B](g12b.md) | Canonical normalization | G12A, G02, first source contract | builder normalizers |
| [G12C](g12c.md) | Bundle validation/manifest | G12B | `market-bundle-builder/bundle_validation.py` |
| [G12D](g12d.md) | Atomic publish/repository | G12C | `market-bundle-builder/local_market_bundle_repository.py` |
| [G12E](g12e.md) | Verified local persisted reader | G12D, WP-06A | `market-data-contracts/local_market_bundle_reader.py` |
| [G12F](g12f.md) | Reader/partition parity | G12E, G07 | parity tooling |
| [G12G](g12g.md) | Canonical revisioned bar aggregation — `PASSED` | G12B–C | `bar_aggregation.py` |
| [G12H](g12h.md) | Rule coverage — readiness `BLOCKED`, Gate `DRAFT` | G12C + profile rule declaration | builder validation |
| [G12I](g12i.md) | Price/availability/revision coverage — readiness `BLOCKED`, Gate `DRAFT` | G12C, G12G + closure declarations | builder validation |
| G12J | Schema migration | real old artifact | trading-domain migration |
| [G12K](g12k.md) | Universe/corporate-action coverage — readiness `BLOCKED`, Gate `DRAFT` | G12C + normalized schemas/closure declarations | builder validation |
| [G12L-*](g12l.md) | Provider source qualification — common contract frozen | applicable G12A–K + real provider evidence | provider-specific slices only |
| [G12L-BINANCE-USDM-MARK-PRICE-KLINES-V1](g12l-binance-usdm-mark-price-klines-v1.md) | First concrete slice — `DRAFT / IN PROGRESS`; real ZIP/checksum and exact G12A identity frozen | G10D, G12A-D + Binance public-data evidence | Builder Binance USD-M source slice |
| G12M-* | Market qualification | market-specific G12L, G07–G10 | runtime qualification |

## Parallelism

After G12C, G12D, G12G, G12H, and G12K may proceed as disjoint research/readiness lanes. Implementation remains single-writer where public schemas, the Acceptance Matrix, architecture policy, or shared fixtures overlap.

G12L's common contract remains provider-neutral. The first concrete slice selects Binance Public Data USD-M daily mark-price klines and freezes one real ZIP/checksum plus its exact G12A identity; provider normalization, revision closure, G12C/D evidence, and adapter acceptance remain in progress. No other market/provider is selected.

Status remains authoritative only in `docs/implementation/acceptance-matrix.md`.
