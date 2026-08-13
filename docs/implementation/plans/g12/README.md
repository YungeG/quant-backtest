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
| G12G | Bar aggregation | G12B–C | builder aggregation |
| G12H | Rule coverage | G12C | builder validation |
| G12I | Price/availability/revision coverage | G12C, G12G | builder validation |
| G12J | Schema migration | real old artifact | trading-domain migration |
| G12K | Universe/corporate-action coverage | G12C | builder validation |
| G12L-* | Provider source adapter | applicable G12A–K | builder adapters |
| G12M-* | Market qualification | market-specific G12L, G07–G10 | runtime qualification |

## Parallelism

After G12C, G12D, G12G, G12H, and G12K may proceed as disjoint research/readiness lanes. Implementation remains single-writer where public schemas, the Acceptance Matrix, architecture policy, or shared fixtures overlap.

Status remains authoritative only in `docs/implementation/acceptance-matrix.md`.
