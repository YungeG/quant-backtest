# China A-share Commission and Tax Primary Sources

## Scope

This note records the official market facts and explicit development conventions used to freeze G08E. G08E covers standard cash-auction A-share transaction handling fees, securities-business regulatory fees, transaction transfer fees, sell-side securities transaction stamp duty, and one caller-supplied development broker commission schedule.

It does not cover block trades, after-hours fixed-price trading, B shares, funds, bonds, Stock Connect, margin/short accounts, broker rebates, provider statement parity, corporate actions, live adapters, deployment authorization, or fee changes outside the finite fixture interval.

## Official market-level charges

### SSE and SZSE transaction handling fee

The exchange notices establish that, effective 2023-08-28, the A-share transaction handling fee changed from `0.0487‰` of transaction value (`0.00487%`) to `0.0341‰` (`0.00341%`), charged on both sides.

Sources:

- SSE 上证发〔2023〕136号, archived as invalid after later rule changes but authoritative for the 2023 interval: <https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/c_20230818_10785262.shtml>
- SZSE notice dated 2023-08-18: <https://www.szse.cn/disclosure/notice/general/t20230818_602805.html>
- SZSE official fee page, which records the same 2023-08-28 transition: <https://www.szse.cn/marketServices/deal/payFees/>

The notices also specify discounts for block trades. G08E v1 does not model block trading and must reject that mechanism rather than apply the auction rate.

### Securities-business regulatory fee

NDRC/MOF 发改价格规〔2018〕917号 sets the securities-business regulatory fee charged to the Shanghai and Shenzhen exchanges at `0.02‰` (`0.002%`) of stock transaction value from 2018-01-01 and repeals the predecessor 2016 schedule. Unlike the temporary institutional-fee exemption in the same notice, the business-fee paragraph has no 2020 expiry. The SZSE official fee page identifies the A-share customer-facing collection as bilateral and on behalf of the CSRC.

Sources:

- NDRC/MOF 发改价格规〔2018〕917号: <https://www.ndrc.gov.cn/xxgk/zcfb/ghxwj/201806/t20180627_960950.html>
- Retrieved-page SHA-256: `sha256:4c8c8426c7cc797a99a86f8d8bea21fef8f1a944d1ef14857286c9784085b3c8`
- NDRC/MOF 发改价格〔2021〕1947号, later regulatory-fee continuity context: <https://www.ndrc.gov.cn/xxgk/zcfb/tz/202201/t20220107_1311590.html>
- SZSE official fee page: <https://www.szse.cn/marketServices/deal/payFees/>
- Retrieved SZSE fee-page SHA-256: `sha256:fbd7df3dfa07778b1318564563d22992f19d06bde415144fef248f27674f03c7`

G08E freezes the 2018 rate only for the narrow August 2023 fixture interval. It does not extrapolate an open-ended current rule.

### ChinaClear transaction transfer fee

ChinaClear states that, effective 2022-04-29, the stock transaction transfer fee for Shanghai and Shenzhen A shares changed from `0.02‰` to `0.01‰` (`0.001%`) of transaction value, charged bilaterally.

Sources:

- ChinaClear 2022-04-28 notice: <https://www.chinaclear.cn/zdjs/gszb/202204/837e3c5031104aa099d6597ba381342a.shtml>
- ChinaClear current Shanghai fee table: <https://www.chinaclear.cn/zdjs/fbzyls/202512/922adc26c2ff4865930c7fb77688bb8a/files/%E4%B8%8A%E6%B5%B7%E5%B8%82%E5%9C%BA%E8%AF%81%E5%88%B8%E7%99%BB%E8%AE%B0%E7%BB%93%E7%AE%97%E4%B8%9A%E5%8A%A1%E6%94%B6%E8%B4%B9%E5%8F%8A%E4%BB%A3%E6%94%B6%E7%A8%8E%E8%B4%B9%E4%B8%80%E8%A7%88%E8%A1%A8.pdf>
- Shanghai table SHA-256: `sha256:84a99e563cb8e84e264c88e3bea2df5f4ac50b1e95330417ec30e2b2566d862f`
- ChinaClear current Shenzhen fee table: <https://www.chinaclear.cn/zdjs/fbzyls/202512/a59388fbfa714c5fa546784891a42e30/files/%E6%B7%B1%E5%9C%B3%E5%B8%82%E5%9C%BA%E8%AF%81%E5%88%B8%E7%99%BB%E8%AE%B0%E7%BB%93%E7%AE%97%E4%B8%9A%E5%8A%A1%E6%94%B6%E8%B4%B9%E5%8F%8A%E4%BB%A3%E6%94%B6%E7%A8%8E%E8%B4%B9%E4%B8%80%E8%A7%88%E8%A1%A8.pdf>
- Shenzhen table SHA-256: `sha256:dff4a06ce20e180f4a85ddae138211dcf7dd3246fb84775453cfd21cbaec6573`

The current ChinaClear tables are corroborating primary references. The result-affecting G08E fixture remains finite and does not treat these pages as a runtime current-rule source.

## Official tax rule

### Sell-only securities transaction stamp duty

The State Taxation Administration's official 12366 answer quotes 财税明电〔2008〕2号: effective 2008-09-19, A-share and B-share securities transaction stamp duty changed from bilateral collection to `1‰` (`0.1%`) charged only to the transferor/seller.

Source:

- Official 12366 answer quoting 财税明电〔2008〕2号: <https://12366.chinatax.gov.cn/nszx/onlinemessage/detail?id=c012f7a11b0e48429e85e861b2682d3e>

财政部、税务总局公告2023年第39号 states that, effective 2023-08-28, securities transaction stamp duty is reduced by half. For the already sell-only `1‰` rule, G08E therefore freezes `0.5‰` (`0.05%`) charged only to the seller from that date.

Source:

- China Government policy page: <https://www.gov.cn/zhengce/zhengceku/202308/content_6900443.htm>

The fixture uses the exact transition from `1‰` sell-only on 2023-08-25 to `0.5‰` sell-only from 2023-08-28. BUY tax applicability is explicitly not applicable; it is not represented by a zero-valued applied tax.

## Ownership boundary

The charges above are market or tax facts. A broker commission rate and minimum commission are not uniform exchange facts. They belong to `ExecutionAccountProfile.account_fee_schedule` and must carry an `AccountFeeScheduleRef` distinct from the market-fee and tax component identities.

G08E uses a synthetic development account schedule only to prove the existing generic machinery:

- net broker commission: `0.3‰` (`0.03%`) of actual filled notional;
- minimum: CNY 5.00 per terminal Order with at least one Fill;
- the schedule is explicitly net of the separately modeled market-level charges;
- it is not attributed to any real broker and is not evidence of a universal Chinese brokerage contract.

A future provider/account adapter must supply its own immutable effective schedule and statement-parity evidence. It must not reuse the development schedule as a real account default.

## Frozen canonical source identities

The implementation RuleBooks must use these exact result-affecting source identities. URLs, retrieval time (`2026-08-08` UTC), and local paths remain provenance; the `source_key/source_hash` pairs are canonical evidence:

| Charge fact | `source_key` | `source_hash` |
| --- | --- | --- |
| SSE 2023 handling-fee transition | `sse.transaction-handling.2023-136` | `sha256:09fc5f031acb829b3810e23196fa77201d9181060209cd6fe6a2fff4d76070bc` |
| SZSE 2023 handling-fee transition | `szse.transaction-handling.2023-08-18` | `sha256:6645a32b6ab297741f22e6b8e959342bb4c9312757d0f1d99de37a0a410d12ba` |
| CSRC regulatory-fee rate | `ndrc.securities-business-regulatory-fee.2018-917` | `sha256:4c8c8426c7cc797a99a86f8d8bea21fef8f1a944d1ef14857286c9784085b3c8` |
| SZSE bilateral regulatory-fee collection | `szse.market-fee-collection.2026-08-08-snapshot` | `sha256:fbd7df3dfa07778b1318564563d22992f19d06bde415144fef248f27674f03c7` |
| ChinaClear Shanghai bilateral fee table | `chinaclear.sh-market-fee-table.2025-12-31` | `sha256:84a99e563cb8e84e264c88e3bea2df5f4ac50b1e95330417ec30e2b2566d862f` |
| ChinaClear transfer-fee transition | `chinaclear.stock-transfer-fee.2022-04-28` | `sha256:68763b8fe13f7fb90f378b077033b692aafc4eca851c78c18a306b001d591a60` |
| Sell-only `1‰` stamp-duty baseline | `sta.12366.stamp-duty.2008-2-quotation` | `sha256:69179c93a4861d2fad5d96d2d8e85b3346e0b70ac8213129959bcb4fa5d3f6ba` |
| 2023 stamp-duty halving | `mof-sta.stamp-duty.2023-39` | `sha256:970711682948365c3f79afc476df67d5f2d29f57ed239f695f1308f45acffdaf` |

The New stamp-duty Band binds both the 2008 baseline source and the 2023 halving source. Market-fee Bands bind source-ref tuples per component: handling uses the venue-specific transition notice; regulatory uses the NDRC rate source plus the venue-specific bilateral-collection source (`chinaclear.sh-market-fee-table.2025-12-31` for XSHG, `szse.market-fee-collection.2026-08-08-snapshot` for XSHE); transfer uses the ChinaClear 2022 notice.

## G08E system conventions

The following are versioned simulation/accounting conventions, not claims that every exchange, clearing participant, or broker rounds identically:

- all frozen rules use typed scaled integers and `fee_fraction` rates;
- each market-fee or tax component is quantized independently to CNY Scale 2 with `RoundingPolicy.HALF_UP`;
- final market fees and stamp duty use `FeeBasisType.FILL`, so each immutable Fill is assessed with the rule effective at its execution time;
- final broker commission uses `FeeBasisType.ORDER`, so actual fills are aggregated only after the Order reaches a terminal state and the CNY 5.00 minimum is applied once;
- reservation uses the approved full-order notional and the same explicit account minimum once, but remains a non-financial `FeeReservationEstimate`;
- because final market/tax components round independently per Fill, caller supplies a positive `maximum_fill_count=N`; the canonical reservation buffer adds `floor(N/2)` CNY cents for each applicable final component (three market components, plus stamp duty for SELL). This is a mathematical rounding bound, not an official fee;
- an Attempt whose actual Fill count exceeds N fails closed before canonical publication; the system may not call an unbounded aggregate estimate conservative;
- partial cancellation releases the difference between the buffered reservation and final assessments; a no-fill cancellation has zero final commission and no `FeeCharged` entry;
- a market/tax rule-book gap or overlap fails closed; no current-rule, nearest-rule, container-order, or account-schedule fallback is allowed;
- official URLs, retrieval timestamps, and local download paths are provenance. Result-affecting identities bind immutable source key/hash values, finite bands, rates, side, basis, quantization, and component/rule-set hashes.

## Frozen fixture interval and exclusions

The golden fixture covers XSHG and XSHE standard CNY cash-auction A shares over a deliberately narrow interval:

- old band: `[2023-08-25T00:00:00+08:00, 2023-08-28T00:00:00+08:00)`;
- new band: `[2023-08-28T00:00:00+08:00, 2023-08-30T00:00:00+08:00)`.

The old/new bands change exchange handling fee and stamp duty. Regulatory and transfer fees remain explicit in both bands. An instant outside this interval is missing coverage, even if a current public fee page exists.

The fixture excludes block-trade discounts, transfer-tax exemptions, risk-warning distinctions not relevant to these rates, non-CNY securities, negotiated rebates, VAT, broker-specific bundled-fee conventions, interest, financing, corporate-action tax, and deployment authorization.
