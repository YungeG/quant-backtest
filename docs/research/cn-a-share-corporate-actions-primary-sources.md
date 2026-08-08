# China A-share Corporate Action Primary Sources

## Scope

This note records the official market and clearing facts used to prepare G08F and G08G. The supported readiness scope is deliberately narrow: standard domestic CNY cash-auction A shares on XSHG and XSHE, final implementation announcements, record-date entitlement, ordinary cash dividends, bonus shares, and capital-reserve capitalization.

G08F covers announcement causality and immutable entitlement from an authoritative historical record-date registered-position snapshot. G08G is not READY: cash payment and share adjustment still require Journal-replayable lot effects, exact total cost-basis conservation, availability conventions, and fact-complete tax/fractional-share fixtures.

This note does not authorize runtime source access, provider selection, Stock Connect, margin/short, pledged or lent shares, B/H shares, funds, preferred shares, rights issues, mergers, reverse splits, capital reductions, differential distributions, issuer self-distribution, live trading, or deployment.

## Official lifecycle facts

### Final implementation announcement

A plan, board resolution, or shareholder-meeting approval is not the final executable lifecycle evidence. The implementation announcement contains the final distribution ratios, eligible scope, equity record date, ex-right/ex-dividend date, payment date, and share-listing date.

Shanghai sources:

- SSE《上市公司自律监管指南第2号——业务办理》第五号《权益分派（2025年4月修订）》requires the issuer to agree implementation arrangements with ChinaClear before submitting the implementation announcement. Sections I.2 and III.1–3 define the implementation process; III.7 specifies the record, ex, payment, and listing schedule.
  - Release: <https://www.sse.com.cn/lawandrules/guide/stock/zbxxpljg/ssgszljg/c/c_20260424_10816642.shtml>
  - Official DOCX: <https://www.sse.com.cn/lawandrules/guide/documents/c/10789664/files/e5b78d32cce4406d9c835a354ade8396.docx>
  - SHA-256: `sha256:2830333711f19875734f6662f506c490429ac2eeba31a74dc52850d556933e40`
- SSE《上市公司自律监管指南第1号——公告格式》第三十六号《上市公司权益分派实施（结果）公告（2025年4月修订）》sections II(b), III, and IV(a)1–2 identify the eligible holders and required dates/terms.
  - Release: <https://www.sse.com.cn/lawandrules/guide/stock/zbxxpljg/ssgszljg/c/c_20260424_10816611.shtml>
  - Official DOCX: <https://www.sse.com.cn/lawandrules/guide/stock/zbxxpljg/ssgszljg/c/10816611/files/47295593f3a84f7dbc2681ef34c008c6.docx>
  - SHA-256: `sha256:b441a51f63ace1c715128324e68dd7c66f00cbc4ad6205924bb5bb516e34b275`

Shenzhen source:

- SZSE《上市公司自律监管指南第2号——公告格式（2026年7月修订）》定期报告类第7号《上市公司分红派息、转增股本实施公告格式》sections II–V and VIII–IX require the final cash/share ratios, record date, ex date, payment/listing dates, eligible holders, ChinaClear confirmation, and revised disclosure for abnormal implementation.
  - Release: <https://www.szse.cn/lawrules/service/share/t20260703_621505.html>
  - Official DOCX: <https://docs.static.szse.cn/www/lawrules/service/share/W020260703564159565953.docx>
  - SHA-256: `sha256:704eea0816d091c5502023fafc91b4ca6fe790b34843ee8b8006041d1a731175`

G08F therefore rejects plan-only, incomplete, cancelled, contradictory, or non-terminal supplied evidence. A revision/supersession chain is not implemented in v1; any non-null supersession reference fails closed rather than selecting by container order. Proving that the supplied Candidate belongs to a complete closed revision set, with no omitted later revision or cancellation, is a G08H/Profile-composition precondition rather than a claim made by G08F alone.

### Record-date eligibility

Ordinary entitlement is based on shareholders registered with ChinaClear after exchange close on the equity record date `R`:

- SSE announcement format No. 36, sections II(b) and IV(a)1–2.
- SZSE announcement format No. 7, sections IV–V.
- ChinaClear Shanghai issuer guide section 2.5.1, pp.24–26, states that ChinaClear produces the rights data and `R`-day holder register after `R` close.
- ChinaClear Shenzhen issuer guide section 2.5, printed pp.18–22 / PDF pp.27–31, includes the `R`-day shareholder register in result reports.

ChinaClear sources:

- 《中国证券登记结算有限责任公司上海分公司证券发行人业务指南》, effective 2026-05-15.
  - Release: <https://www.chinaclear.cn/zdjs/shfgz/202605/0c6a366270c94f19b3f75b89076062d7.shtml>
  - Official PDF: <https://www.chinaclear.cn/zdjs/dsh/202605/ceb9d10913fd42238e756ee3ee05d9a0/files/%E4%B8%AD%E5%9B%BD%E8%AF%81%E5%88%B8%E7%99%BB%E8%AE%B0%E7%BB%93%E7%AE%97%E6%9C%89%E9%99%90%E8%B4%A3%E4%BB%BB%E5%85%AC%E5%8F%B8%E4%B8%8A%E6%B5%B7%E5%88%86%E5%85%AC%E5%8F%B8%E8%AF%81%E5%88%B8%E5%8F%91%E8%A1%8C%E4%BA%BA%E4%B8%9A%E5%8A%A1%E6%8C%87%E5%8D%97.pdf>
  - Document ID: `ceb9d10913fd42238e756ee3ee05d9a0`
  - SHA-256: `sha256:2e0947b9a19b9962c8a43d603b722e907fbd47d7615be5643be1005661f00ec8`
- 《中国证券登记结算有限责任公司深圳分公司证券发行人业务指南》, effective 2025-12-31.
  - Release: <https://www.chinaclear.cn/zdjs/szfgsgg/202512/3e5c7318f96148b29faacb9d8f8df5ec.shtml>
  - Official PDF: <https://www.chinaclear.cn/zdjs/dsz/202512/fb54cbc97d61460288d48d079bb9f72c/files/%E4%B8%AD%E5%9B%BD%E8%AF%81%E5%88%B8%E7%99%BB%E8%AE%B0%E7%BB%93%E7%AE%97%E6%9C%89%E9%99%90%E8%B4%A3%E4%BB%BB%E5%85%AC%E5%8F%B8%E6%B7%B1%E5%9C%B3%E5%88%86%E5%85%AC%E5%8F%B8%E8%AF%81%E5%88%B8%E5%8F%91%E8%A1%8C%E4%BA%BA%E4%B8%9A%E5%8A%A1%E6%8C%87%E5%8D%97.pdf>
  - Document ID: `fb54cbc97d61460288d48d079bb9f72c`
  - SHA-256: `sha256:e8db1f9761b083542d72568a25dcbab02b5d0e86d41309ca108eb362c822e902`

The authoritative G08F basis is therefore an immutable historical registered-position snapshot at `R` close, not a later current Portfolio, Ledger balance, sellable balance, Order, Fill, or Bar. A later correction would require explicit superseding register evidence; v1 rejects revisions instead of silently rewriting a captured entitlement.

### Ex-right/ex-dividend date

Both current trading rules establish ordinary ex-right/ex-dividend treatment on the trading day following `R`:

- SSE《上海证券交易所交易规则（2026年修订）》上证发〔2026〕41号, clauses 4.3.1–4.3.3, printed p.24.
  - Release: <https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20260424_10816492.shtml>
  - Official DOCX: <https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/10816492/files/704204728fe74fff89de4f16efda4791.docx>
  - SHA-256: `sha256:fc922c433438b2636cb631eab25cca405209712acbb6aaded768c45456ff8888`
- SZSE《深圳证券交易所交易规则（2026年修订）》深证上〔2026〕551号, clauses 4.4.1–4.4.3, printed p.26.
  - Release: <https://www.szse.cn/lawrules/rule/trade/current/t20260424_620190.html>
  - Official PDF: <https://docs.static.szse.cn/www/lawrules/rule/trade/current/W020260424690713155663.pdf>
  - SHA-256: `sha256:9b66f8b0db70f84a25ef1ccb4ee2351001724e408117552d75f6d8993483c586`

The ex reference price is a market-rule/reference-price fact. It does not authorize rewriting actual OHLC, executed prices, or historical raw tradable prices.

### Payment and listing are distinct facts

The implementation announcement supplies record, ex, payment, and listing dates as distinct lifecycle facts. Ordinary current schedules commonly place ex/payment/listing on `R+1`, but G08G must consume the declared dates and evidence rather than infer them only from entitlement.

ChinaClear Shanghai section 2.5.2 and ChinaClear Shenzhen section 2.5.3 establish ordinary payment through settlement participants on the payment date. Both guides also state that insufficient issuer funds suspend distribution. Exact intraday retail cash reuse time is not established.

For ordinary bonus/capitalization shares, the reviewed guides support `R+1` listing in the current narrow scope. They do not establish a precise intraday account-registration timestamp. Any pre-open adjustment timing would therefore be an explicit development convention.

## Fractional shares and cash precision

ChinaClear Shanghai section 2.5.1(四)7 and Shenzhen section 2.5.4(十) describe whole-share allocation based on the population of fractional entitlements; equal fractions may require clearing-system ordering/randomness. Delivered quantity cannot be reconstructed from one account's holding and ratio alone.

G08F/G08G must not invent floor, half-up, pro-rata, or cash-in-lieu behavior. A fractional result requires authoritative delivered-quantity evidence or fails closed.

ChinaClear Shenzhen section 2.5.4(九) states that cash below CNY 0.01 is truncated. An equivalent current Shanghai per-investor account-total rule was not established. The frozen development fixture therefore uses per-share amounts and quantities that produce exact CNY cents on both venues; any sub-cent result fails closed.

## Dividend and share-distribution tax

The reviewed tax sources show that corporate-action tax is not a simple payment-time percentage:

- MOF/STA 财税〔2015〕101号 clauses 1–2: ordinary domestic individuals holding listed shares for one year or less are generally not withheld at distribution; tax is calculated and collected after a later transfer according to holding period.
  - <https://szs.mof.gov.cn/zhengcefabu/201509/t20150907_1452683.htm>
  - Retrieved-page SHA-256: `sha256:cc70cf3a3fa8921c533799b6bbe8a6d1f36895cdb00bda93709e7aff2f2838ba`
- MOF/STA 财税〔2012〕85号 clauses 3, 6, and 7 retain FIFO/end-of-day holding-period and acquisition/transfer rules.
  - <https://szs.mof.gov.cn/zhengcefabu/201211/t20121116_697495.htm>
  - Retrieved-page SHA-256: `sha256:e8397ee27dfbe5f76f1e20af1ebfc2b0e18541976c489976b060ff5626a6114e`
- STA 国税发〔1997〕198号 clauses 1–2 distinguish capital-reserve conversion from taxable bonus shares.
  - <http://fgk.chinatax.gov.cn/zcfgk/c100012/c5193235/content.html>
  - Retrieved-page SHA-256: `sha256:817268b968f07adfcbc2393a25da1b892bf48ffd61124ef227721dc3961079d1`
- STA 国税函〔1998〕289号 clause 2 limits the capital-reserve exemption to qualifying share-premium issuance income.
  - <http://fgk.chinatax.gov.cn/zcfgk/c100012/c5193247/content.html>
  - Retrieved-page SHA-256: `sha256:ee469900d8f3fe7cb561176288aadb5e572ad15feaf7dff987d1c91a91ca8647`

G08F captures gross entitlement only. G08G remains DRAFT and must not infer payment-time withholding. Taxable bonus-share deferred basis and later-transfer withholding require a separate fact-complete account-tax contract.

## Frozen G08F result-affecting source identities

Official URLs and retrieval time (`2026-08-08` UTC) remain provenance. A G08F RuleBook Band binds the following canonical source identities:

| Fact | `source_key` | `source_hash` |
| --- | --- | --- |
| SSE current ex/record treatment | `sse.trading-rules.2026-41.corporate-actions` | `sha256:fc922c433438b2636cb631eab25cca405209712acbb6aaded768c45456ff8888` |
| SSE implementation process | `sse.distribution-guide.2025-document-5` | `sha256:2830333711f19875734f6662f506c490429ac2eeba31a74dc52850d556933e40` |
| SSE eligible-holder announcement format | `sse.announcement-format.2025-36` | `sha256:b441a51f63ace1c715128324e68dd7c66f00cbc4ad6205924bb5bb516e34b275` |
| ChinaClear Shanghai issuer guide | `chinaclear.sh-issuer-guide.2026-33` | `sha256:2e0947b9a19b9962c8a43d603b722e907fbd47d7615be5643be1005661f00ec8` |
| SZSE current ex/record treatment | `szse.trading-rules.2026-551.corporate-actions` | `sha256:9b66f8b0db70f84a25ef1ccb4ee2351001724e408117552d75f6d8993483c586` |
| SZSE implementation announcement format | `szse.announcement-format.2026-7` | `sha256:704eea0816d091c5502023fafc91b4ca6fe790b34843ee8b8006041d1a731175` |
| ChinaClear Shenzhen issuer guide | `chinaclear.sz-issuer-guide.2025-68` | `sha256:e8db1f9761b083542d72568a25dcbab02b5d0e86d41309ca108eb362c822e902` |

## G08F system conventions

The following are versioned development conventions, not official intraday processing claims:

- Announcement is a normal immutable `MarketEvent`: `event_time` is the publication event, `available_time` is first lawful/data availability, and future record/ex/payment/listing dates remain payload terms. The invariant `available_time >= event_time` is unchanged. The concrete Candidate retains the source Event's complete `timeline_instant = SimulationInstant(available_time, phase, source_sequence)`; availability and capture comparisons use that total order, not UTC time alone.
- The record/eligibility boundary is the known XSHG/XSHE session close at local 15:00 on `R`, represented by `TimelinePhase(rank=100, code="corporate_action_record")` and `SourceSequence(0)`. This is an engine ordering boundary, not a claim that ChinaClear completes registration at exactly 15:00.
- The registered-position snapshot may become available after that eligibility boundary. Entitlement records both `eligibility_instant` and `captured_at`; it may not be captured before the announcement and registered snapshot are available.
- The snapshot is authoritative account/register evidence and carries register-series, revision, supersession, and source identities/hashes. Registered quantity must be non-negative Scale 0. G08F rejects a supplied non-null supersession reference and never substitutes a later Portfolio/Ledger/current Position. The synthetic fixture uses a development register source and does not claim provider parity; G08H must prove the complete closed register-revision set.
- G08F supports only final implementation announcements with no supplied supersession chain. Cash requires a Payment date; bonus/capitalization requires a Listing date; every final Action requires Record and Ex dates. In the frozen current-rule interval, each declared applicable Ex/Payment/Listing date must equal the first known G08A TradingDate after `R`; fields remain mandatory and are validated, not silently inferred. Plan-only, cancelled, contradictory, late-after-record, or incomplete supplied evidence fails closed; G08H must prove announcement revision-set closure.
- Every supplied cash/share distribution component must be strictly positive. Bonus/capitalization Rate basis is exactly `shares_per_share`. Gross cash uses CNY Scale 2 and must be exact; share ratios must produce integer Scale-0 quantities. Unsupported basis, negative terms/quantities, fractional shares, or sub-cent results fail closed.
- Ordinary-vs-preferred classification, cash-auction mechanism, B/H classification, Stock Connect, margin/short, lending/repo, pledge/freeze, restricted/pre-IPO holdings, differential distributions, and issuer self-distribution are not observable in the v1 Instrument/Candidate/Query. G08H/Profile composition must block those contexts; G08F validates only Venue, broad Equity type, currencies, supported action terms, and supplied evidence, and must not infer or claim the unobservable contexts were qualified.
- G08F emits no Journal Entry and changes no Ledger, lot, Settlement, Availability, Reservation, Order, Strategy, Runtime, or deployment state.

## Frozen development fixture

The finite RuleBook coverage is `[2026-07-06T00:00:00+08:00, 2026-07-31T00:00:00+08:00)`. Outside this interval, missing or overlapping coverage fails closed.

### `CA-XSHE-001` combined distribution

- synthetic final implementation announcement available at `2026-07-13T18:00:00+08:00`, `TimelinePhase(20, "corporate_action_announcement")`, `SourceSequence(1)`;
- record date `2026-07-16`; eligibility boundary local 15:00;
- registered snapshot available/captured at `2026-07-16T18:00:00+08:00`;
- declared ex/payment/listing date `2026-07-17`;
- CNY `0.10` cash, `0.10` bonus share, and `0.20` capitalization share per registered share;
- Account A registered quantity `700`: gross CNY `70.00`, bonus `70`, capitalization `140`;
- Account B registered quantity `0`: canonical zero entitlement; a later ex-date purchase of `500` creates no entitlement.

### `CA-XSHG-001` cash-only distribution

- synthetic final implementation announcement available at `2026-07-14T18:00:00+08:00`, `TimelinePhase(20, "corporate_action_announcement")`, `SourceSequence(1)`;
- record date `2026-07-17`; eligibility boundary local 15:00;
- registered snapshot available/captured at `2026-07-17T18:00:00+08:00`;
- declared ex/payment date `2026-07-20`;
- CNY `0.20` cash per registered share;
- registered quantity `1,000`: gross CNY `200.00`;
- a later zero current holding does not alter the entitlement.

## G08G readiness blockers

G08G remains DRAFT until all of the following are frozen:

1. Generic Journal/Ledger replay must make Position Lot create/replace/close effects authoritative. The current Ledger rejects lots and Runtime maintains mutable lot side-state.
2. `PositionLot` needs an exact authoritative total cost-basis representation; unit cost alone cannot conserve a repeating ratio such as 3-for-2.
3. Fill accounting and corporate-action adjustment must emit the same replayable lot-effect contract. An integer account-level entitlement may still be fractional when allocated across multiple Lots, so READY requires authoritative per-Lot allocation evidence or an exactly-one-eligible-Lot v1 restriction.
4. New-share sellability and paid-cash tradable/withdrawable availability must be explicit and bound to component identity.
5. Fractional delivered quantities require authoritative account-level evidence; no local rounding algorithm may be invented.
6. Corporate-action tax needs a typed disposition and owner. At minimum it must distinguish `NOT_APPLICABLE`, `APPLIED`, and `DEFERRED_UNSUPPORTED`; G08G owns the disposition/translation, while G08H/Runtime composition must block a later taxable transfer for `DEFERRED_UNSUPPORTED`. Without that guard, v1 must exclude ordinary-individual deferred-tax cases and accept only explicit `NOT_APPLICABLE` evidence.
7. Effective/payment/listing delay or suspension evidence must be explicit. Entitlement alone cannot cause automatic adjustment or payment.
8. Raw tradable prices remain unchanged; ex-reference metadata cannot rewrite execution bars.
