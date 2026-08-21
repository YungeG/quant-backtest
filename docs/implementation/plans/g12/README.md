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
| [G12-ACQ-TOOLS-V1](../../provider-acquisition-tools.md) | Backtest-owned Binance/Tushare source acquisition — `PASSED`; immutable commit `6f0bd99a93a349924996eb26708fbb0ac6fecf17` | G12A | `tools/acquisition/` |
| G12-ACQ-TUSHARE-CALENDAR-V1 | Additive exact `trade_cal` acquisition — `PASSED`; immutable commit `10638db8225f68256c027b1dd1373bacff0d112c` | G12A, acquisition tools | `tools/acquisition/cn_a_share_tushare_trade_calendar.py` |
| [G12L-TUSHARE-CN-A-SHARE-AUTHORITY-ACQUISITION-V1](g12l-tushare-cn-a-share-authority-acquisition-v1.md) | Additive listing/name/adjustment/dividend source capture — `PASSED`; source `57afefb8283ff6fbfdd9e4f2579c5091171dc18e`; snapshot `sha256:bd8ae548949696f1c98f8a20b5c8653f64121fc2eee61c1ff2ac21a97d248c0d`; all qualification remains false | G12A, acquisition tools, trade calendar | `tools/acquisition/cn_a_share_tushare_authority.py` |
| [G12B](g12b.md) | Canonical normalization | G12A, G02, first source contract | builder normalizers |
| [G12B-TUSHARE-CN-A-SHARE-DAILY-V1](g12b-tushare-cn-a-share-daily-v1.md) | Purpose-free raw daily Bar plus explicit execution-reference/valuation projections — `PASSED`; commit `373817b762fbe0d68b286577e0396107694cc9a1` | G12A, G12B, G12G + frozen Tushare evidence | internal Builder Tushare normalizer |
| [G12CD-TUSHARE-CN-A-SHARE-DAILY-PUBLICATION-V1](g12cd-tushare-cn-a-share-daily-publication-v1.md) | One internal Tushare result→Event projection composed through unchanged G12C/D — `PASSED`; source `7400cad6531b2687ffb150959cbf534c6797359e` | G12B Tushare result, G12C, G12D | internal Builder projection |
| [G12I-TUSHARE-CN-A-SHARE-DAILY-PURPOSE-SCOPE-V1](g12i-tushare-cn-a-share-daily-purpose-scope-v1.md) | Exact finite EXECUTION_REFERENCE and VALUATION requirements bound to the accepted publication — `PASSED`; evidence `5fd8e94`; availability/revision qualification remains false | G12I declarations, Tushare publication v1 | static provider-specific evidence |
| [G12CD-TUSHARE-CN-A-SHARE-DAILY-PUBLICATION-V2](g12cd-tushare-cn-a-share-daily-publication-v2.md) | Additive one-instrument catalog-bound publication — `PASSED`; source `5909018`; current metadata only, no historical listing/survivorship authority | Tushare publication v1, G12C, G12D | internal Builder projection |
| [G12CD-CN-A-SHARE-DEVELOPMENT-RULE-AUTHORITIES-V1](g12cd-cn-a-share-development-rule-authorities-v1.md) | Lossless five-dimension G08H development-rule publication through unchanged G12C/D — `PASSED`; source `832f53a74d3f74436ecae8672bd1c0dd3530c814`; all provider/G12H/decision/deployment qualification false | G08H, G12C, G12D | internal Builder projection |
| [G12C](g12c.md) | Bundle validation/manifest | G12B | `market-bundle-builder/bundle_validation.py` |
| [G12D](g12d.md) | Atomic publish/repository | G12C | `market-bundle-builder/local_market_bundle_repository.py` |
| [G12E](g12e.md) | Verified local persisted reader | G12D, WP-06A | `market-data-contracts/local_market_bundle_reader.py` |
| [G12F](g12f.md) | Reader/partition parity | G12E, G07 | parity tooling |
| [G12G](g12g.md) | Canonical revisioned bar aggregation — `PASSED` | G12B–C | `bar_aggregation.py` |
| [G12H](g12h.md) | Rule coverage — `DRAFT / BLOCKED`; effective-until-authoritatively-superseded semantics approved, but exact current fixture remains `COVERAGE_GAP / market_fees` | G12C + aligned five-dimension rule authority | builder validation |
| [G12H-EFFECTIVE-UNTIL-SUPERSEDED-V2](g12h-effective-until-superseded-v2.md) | Additive strict successor-closure path — `BLOCKED`; route/product V2A/V2B/V2C PASSED, but complete predecessor/endpoint/successor authority is unavailable | G08E-ROUTE-PRODUCT-FEE-V2C plus official predecessor/endpoint/index evidence | staged contract/research/build publication |
| [G12H-CURRENT-SELECTED-DEVELOPMENT-V1](g12h-current-selected-development-v1.md) | Additive option-B development path — D1-D3 `PASSED` at `cdc5a29133bbc0b863ec409219fb50bd0b299c77`; D4 coverage `PASSED` at `0215ed3a369bff10a64830c462c569b378914670`; D5 Runtime fan-in `PASSED` at `d1a472091deb7d844e696a814e9e52e46976ece4`; D6 financial-dispatch journey `PASSED` at `54951d1d181274c7597c1c5b7cff2f81a4bd0f8f`; all official/provider/rule-qualification/decision/live/deployment flags stay false | ADR 0007, G12H live-status API probes, G08E-ROUTE-PRODUCT-FEE-V2C, G12C/D | snapshot + existing v2 values + internal Builder publication + coverage analyzer + off-root Runtime binding + dispatcher/ledger journey |
| [G12I](g12i.md) | Price/availability/revision coverage — readiness `BLOCKED`, Gate `DRAFT` | G12C, G12G + closure declarations | builder validation |
| G12J | Schema migration | real old artifact | trading-domain migration |
| [G12K](g12k.md) | Universe/corporate-action coverage — `DRAFT / D1-D2 DEVELOPMENT PASSED`; [July-2026 development v1](g12k-july-2026-development-coverage-v1.md) contract `24b88d8`, analyzer `a9be1d1`; provider/history/survivorship qualification remains BLOCKED | G12C + normalized schemas/closure declarations | builder validation |
| [G12L-*](g12l.md) | Provider source qualification — common contract frozen | applicable G12A–K + real provider evidence | provider-specific slices only |
| [G12L-BINANCE-USDM-MARK-PRICE-KLINES-V1](g12l-binance-usdm-mark-price-klines-v1.md) | First concrete slice — `PASSED`; immutable commit `47d59e40081555ab9b555c3e632070a517509436` | G10D, G12A-D + Binance public-data evidence | Builder Binance USD-M source slice |
| [G12L-BINANCE-USDM-AGGTRADES-V1](g12l-binance-usdm-aggtrades-v1.md) | Second concrete slice — `PASSED`; immutable commit `981429b4f0ff5fa219ccc8bc991458072b025bf8` | G10D, G12A-D + Binance public-data evidence | Builder Binance USD-M source slice |
| [G12L-BINANCE-USDM-FUNDING-RATE-V1](g12l-binance-usdm-funding-rate-v1.md) | Third concrete slice — `PASSED`; immutable commit `ebd91f746c4a065ca06dba89d847e7d41ab06331` | G10E, G12A-D + Binance public-data evidence | Builder Binance USD-M source slice |
| [G12L-BINANCE-USDM-FUNDING-HISTORY-V1](g12l-binance-usdm-funding-history-v1.md) | Exact rate+mark REST evidence — `DRAFT / BLOCKED`; no immutable provider revision closure | G10E, G12A + Binance API evidence | Builder Binance USD-M source slice |
| [G12L-TUSHARE-CN-A-SHARE-DAILY-LISTING-V1](g12l-tushare-cn-a-share-daily-listing-v1.md) | First real A-share capture — `DRAFT / BLOCKED`; source/G12A/parity, event-time, numeric units, and G12B purpose contract frozen | G12A, acquisition tools + Tushare evidence | Builder China A-share source slice |
| [G12M-SOURCE-BOUNDED-QUALIFICATION-V1](g12m-source-bounded-qualification-v1.md) | Governance accepted; implementation contract waits on provider slices | G12I SZSE, G12K SZSE/CNINFO, Binance FAPI observed-as-of | Runtime read-only qualification |

## Parallelism

After G12C, G12D, G12G, G12H, and G12K may proceed as disjoint research/readiness lanes. Implementation remains single-writer where public schemas, the Acceptance Matrix, architecture policy, or shared fixtures overlap.

G12L's common contract remains provider-neutral. The first concrete slice PASSES Binance Public Data USD-M daily mark-price klines with real ZIP/checksum bytes, exact G12A identity, conservative late availability, purpose-separated normalization, and G12C/D evidence. The second concrete slice PASSES Binance USD-M daily aggregate trades with real source/G12A, EXECUTION_REFERENCE normalization, and G12C/D publication evidence. The third PASSED slice freezes rate-only monthly funding archives. A separate exact rate+mark REST capture remains BLOCKED because Binance exposes no immutable revision/correction closure. No other market/provider is selected.

Status remains authoritative only in `docs/implementation/acceptance-matrix.md`.
