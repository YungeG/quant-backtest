# 000703 January 2024 statutory-fee development authority v1

## Scope

This is the finite development projection authorized by ADR 0011, and only covers:

```text
[2024-01-02T00:00:00+08:00, 2024-02-01T00:00:00+08:00)
XSHE + EQUITY + CNY/CNY + AUCTION + DOMESTIC + ORDINARY_A_SHARE
basis: trade_notional
```

`DOMESTIC` means an order submitted through a mainland securities company directly to XSHE. It excludes northbound Stock Connect submission through HKEX securities-trading-service companies.

## Frozen economics

| Component | Buy | Sell | Authority-effective from |
| --- | ---: | ---: | --- |
| SZSE handling | 0.0341‰ | 0.0341‰ | 2023-08-28 |
| CSRC regulatory | 0.02‰ | 0.02‰ | 2018-01-01 |
| ChinaClear transfer | 0.01‰ | 0.01‰ | 2022-04-29 |
| Stock Connect / HKSCC transfer | not applicable | not applicable | finite domestic exclusion |
| Stamp duty | 0 | 0.5‰ | 2023-08-28 |
| **Total** | **0.0641‰** | **0.5641‰** | |

The exact primary-response bytes, request/final URL, headers, redirect chain, receipt, and hash for every source are frozen in [`../../evidence/000703-january-2024-statutory-fee-development-v1/snapshot.json`](../../evidence/000703-january-2024-statutory-fee-development-v1/snapshot.json). The stamp-duty-law capture binds its official `印花税税目税率表.ppt` attachment; the retained securities-transaction slide is derived byte-for-byte and transcribed as `成交金额的千分之一` (`1‰`) in the snapshot's extraction record. Announcement 39 halves that rate to `0.5‰`. The ChinaClear original 2022 notice retains the operative sentence: the A-share transfer fee was reduced to `0.01‰` bilateral from 2022-04-29.

## Status and boundary

This is a current-official **development projection**, not official successor closure. It is not decision-grade, live-eligible, deployment-authorized, an account invoice model, or a RuleBook. Brokerage commission, billing aggregation, rounding, minimums, rebates, and non-domestic routes remain unbound.

Every known result-affecting candidate in the frozen snapshot has an explicit disposition; unresolved candidates fail closed. The NDRC 2021 Beijing-exchange extension has no XSHE economic effect. The retained ChinaClear Stock Connect description supports the explicit domestic-route exclusion rather than treating HKSCC as an unexplained zero charge.
