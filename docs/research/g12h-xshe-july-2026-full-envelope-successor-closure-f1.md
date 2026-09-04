# G12H XSHE July-2026 Full-Envelope Successor Closure F1

## Status

**BLOCKED.** F1 must not produce a closure artifact, finite July-2026 RuleBook, fixture, declaration, publication, registry entry, or qualification claim from the reviewed evidence.

The decisive blocker is a route-and-product scope mismatch, independent of the still-incomplete successor-index evidence:

> Northbound Shenzhen Stock Connect has an additional HKSCC transfer fee of **0.002% (`0.02‰`) of gross trade value per side**, in addition to the ChinaClear transfer fee of **0.001% (`0.01‰`) per side**. Ordinary domestic XSHE access has the ChinaClear fee but not the HKSCC fee. Separately, SZSE preferred-stock handling is **80% of the ordinary-stock handling standard**, while Northbound ETFs use **0.004% (`0.04‰`) handling per purchase or sale** with securities-management fee, ChinaClear transfer fee, and stamp duty waived. `CnAShareCashFeeRuleQuery` distinguishes neither selected access route nor execution fee product class, so one access/product-blind `CnAShareMarketFeeRuleBook` is necessarily wrong for at least one supported route/product combination.

This is `SCOPE_MISMATCH` / `AUTHORITY_SCOPE_GAP`, not a qualified closure. Stock Connect and non-ordinary-A-share product classes must not be silently excluded or assigned ordinary A-share rates.

## Reviewed contract and target

This report freezes the result of reviewing:

- [ADR 0004](../adr/0004-official-rules-effective-until-authoritatively-superseded.md);
- [G12H effective-until-superseded v2 plan](../implementation/plans/g12/g12h-effective-until-superseded-v2.md);
- [prior XSHE July-2026 fee/tax research](g12h-xshe-july-2026-fee-tax-authority-primary-sources.md);
- the exact local types in `packages/trading-kernel/src/crypto_quant_trading/profiles/cn_a_share/commission_tax.py`.

The preserved target is:

```text
UTC:           [2026-07-05T16:00:00Z, 2026-07-30T16:00:00Z)
Asia/Shanghai: [2026-07-06 00:00:00+08:00, 2026-07-31 00:00:00+08:00)
```

ADR 0004 and the v2 plan define the F1 success envelope as XSHE, `InstrumentType.EQUITY`, CNY quote and settlement, `AUCTION`, all boards, all query-indistinguishable access channels, and `trade_notional` basis.

### Exact local representability limit

`CnAShareCashFeeRuleQuery` contains only:

```text
instrument: InstrumentDefinition
side: OrderSide
effective_at: UtcInstant
trade_mechanism: CnAShareFeeTradeMechanism
```

The policy validates venue, equity instrument type, CNY quote/settlement currencies, and auction mechanism. It does not receive or derive board, selected access route, or execution fee product class. Local `InstrumentType` has no preferred-stock or ETF member; this fee path accepts only the broad `EQUITY` classification. Any ordinary share, preferred stock, or ETF admitted through that classification is fee-product-indistinguishable to the query. `InstrumentId.stable_key` is identity, not an execution-enforced fee classification, and must not be parsed to guess product semantics. Resolution selects a finite Band only by `venue_id` and `effective_at`.

`CnAShareMarketFeeBand` contains one rate each for `handling_rate`, `regulatory_rate`, and `transfer_rate`. The resulting execution rules apply those rates on order/fill notional. It has no route/product discriminator and cannot represent participant portfolio value, clearing instructions, settlement messages, or other non-notional bases. Adding access channel alone is therefore insufficient: v2 fee evaluation must also receive an immutable, execution-enforced fee product class.

## Route and product matrix

The figures below are target-state candidates supported by the identified first-party materials. They are **not** qualified July-2026 closure bands because successor/correction inventory is incomplete and exact closure evidence representations were not frozen.

### Ordinary A-share route comparison

| Component | Ordinary domestic XSHE ordinary A share | Northbound Shenzhen Stock Connect ordinary A share | Basis and side | F1 disposition |
| --- | ---: | ---: | --- | --- |
| SZSE transaction handling fee | `0.00341%` (`0.0341‰`) | `0.00341%` (`0.0341‰`) | consideration; purchase and sale | Candidate economics match for ordinary A shares; successor closure incomplete |
| CSRC securities-management/regulatory fee | `0.002%` (`0.02‰`) | `0.002%` (`0.02‰`) | consideration; purchase and sale | Candidate economics match; controlling-rate and investor-collection closure incomplete |
| ChinaClear transfer fee | `0.001%` (`0.01‰`) | `0.001%` (`0.01‰`) | consideration; purchase and sale | Candidate economics match; successor closure incomplete |
| **HKSCC China Connect transfer fee** | **not applicable** | **`0.002%` (`0.02‰`) additional** | gross value of each China Connect Securities Trade; per side | **Blocker: execution-linked and route-specific, but query is route-blind** |
| Securities transaction stamp duty | `0.05%` (`0.5‰`) | `0.05%` (`0.5‰`) | consideration; seller/transferor only | Candidate economics match for ordinary A shares; statutory and half-collection successor closure incomplete |
| Buy-side notional subtotal of the rows above | `0.00641%` (`0.0641‰`) | `0.00841%` (`0.0841‰`) | arithmetic candidate only | Differs by the HKSCC `0.002%`; cannot share one route-blind RuleBook |
| Sell-side notional subtotal including stamp duty | `0.05641%` (`0.5641‰`) | `0.05841%` (`0.5841‰`) | arithmetic candidate only | Differs by the HKSCC `0.002%`; not a qualified charge schedule |

### Product-class comparison inside the current product-blind path

| Route/product candidate | Handling fee | Securities-management fee | ChinaClear transfer fee | Stamp duty | Separate HKSCC transfer | Representability disposition |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Ordinary domestic XSHE ordinary A share | `0.00341%` (`0.0341‰`) | `0.002%` (`0.02‰`) | `0.001%` (`0.01‰`) | `0.05%` (`0.5‰`) seller-only | not applicable | Ordinary-A-share candidate only; must not be generalized |
| Ordinary domestic XSHE preferred stock | **80% of ordinary-stock handling = `0.002728%` (`0.02728‰`)** | not reclosed by this increment | not reclosed by this increment | not reclosed by this increment | not applicable | **Product blocker:** the SZSE page states 80% during the pilot; derived decimal is bilateral because the ordinary handling standard is bilateral |
| Northbound XSHE ordinary A share | `0.00341%` (`0.0341‰`) | `0.002%` (`0.02‰`) | `0.001%` (`0.01‰`) | `0.05%` (`0.5‰`) seller-only | `0.002%` (`0.02‰`) additional candidate | Route and product candidate; closure incomplete |
| Northbound XSHE-listed ETF | **`0.004%` (`0.04‰`) per purchase or sale** | **waived** | **waived** | **waived** | section 21's generic `0.002%` China Connect trade candidate remains separate; the transaction table does not state an ETF waiver for it | **Product blocker:** handling differs and three ordinary-A-share components are waived |

The first-party [HKEX Northbound transaction page](https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Fees/Securities-(Stock-Connect)/Trading/Transactions?sc_lang=en) presents separate A-share and ETF columns. It states ETF handling at `0.004%` of consideration for each purchase or sale and marks the securities-management fee, ChinaClear transfer fee, and stamp duty as waived for ETFs. The waivers in that transaction table must not be silently extended to the separate HKSCC section 21 fee.

The SZSE [January-2026 fee table](https://www.szse.cn/marketServices/deal/payFees/index.html) states that preferred-stock handling during the pilot is charged at 80% of the ordinary-stock standard. Applying the displayed bilateral ordinary-stock standard of `0.0341‰` gives the arithmetic candidate `0.02728‰` (`0.002728%`) per side. The page states the 80% relation; the decimal is a transparent derivation, not a separately printed rate.

The ordinary-A-share subtotal rows are arithmetic comparisons, not installation-ready rates. They exclude broker commission and the non-notional portfolio/instruction charges.

## Decisive source fact

[HKSCC Operational Procedures section 21](https://www.hkex.com.hk/-/media/HKEX-Market/Services/Rules-and-Forms-and-Fees/Rules/HKSCC/Operational-Procedures/SEC21.pdf) states that each China Connect Clearing Participant pays `0.002%` of the gross value of each China Connect Securities Trade and explicitly says the fee is **in addition to** the transfer fee payable under SEHK Rules 14A11 and 14B11.

The separate ChinaClear rate is `0.001%` per purchase or sale. The Northbound transition to that rate effective `2022-04-29` is stated in [HKSCC circular CD/OES/CCASS/017/2022](https://www.hkex.com.hk/-/media/HKEX-Market/Services/Circulars-and-Notices/Participant-and-Members-Circulars/HKSCC/2022/ce_HKSCC_SET_017_2022_.pdf) and the underlying [ChinaClear notice](https://www.chinaclear.cn/zdjs/gszb/202204/837e3c5031104aa099d6597ba381342a.shtml).

Therefore:

```text
ordinary domestic stock-transfer rate: 0.001% per side
Northbound stock-transfer economics:    0.001% ChinaClear + 0.002% HKSCC
                                      = 0.003% per side
```

Putting `0.001%` in the single local `transfer_rate` undercharges Northbound ordinary A shares. Putting `0.003%` there overcharges ordinary domestic access. Moving the HKSCC amount into another local lineage does not repair the mismatch because every lineage resolves from the same route-blind query.

Route discrimination alone still does not close F1. On the same Northbound route, an ordinary A share uses `0.00341%` handling plus non-waived securities-management, ChinaClear transfer, and seller stamp duty, while an ETF uses `0.004%` handling and waives those three components. On ordinary domestic XSHE access, preferred-stock handling is 80% of ordinary-stock handling. A valid reusable v2 contract must therefore bind both selected access route and execution fee product class before fee evaluation.

## Access-specific non-notional limitations

The HKSCC [Northbound clearing and settlement fee page](https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Fees/Securities-(Stock-Connect)/Clearing-and-Settlement?sc_lang=en) and section 21 also identify costs that are not uniform per-trade notional rates:

- a tiered portfolio fee accrued daily on aggregate China Connect holdings, from `0.008%` per annum for the first HK$50 billion through `0.003%` for the portion above HK$1,000 billion, collected monthly;
- money-settlement charges such as `HK$0.50` for each applicable CPI;
- SI/STI, cash-prepayment, collateral, safekeeping, corporate-action, and other participant/instruction fees in specified circumstances.

These costs are a separate limitation from the route/product execution-fee blockers. The present query and Band types model execution-linked notional rates; they do not carry participant portfolio state or settlement-instruction context. Whether each participant-level charge belongs in the product's promised cost envelope requires an explicit policy contract. It must not be silently folded into a notional rate or silently omitted under a claim of full route/product cost coverage.

## Candidate inventory and dispositions

| Candidate or official act | Published/effective state | Candidate economics or relevance | Disposition |
| --- | --- | --- | --- |
| SZSE handling predecessor | before `2023-08-28` | `0.00487%` bilateral | Before target; predecessor identified, but exact predecessor representation was not frozen here |
| [SZSE handling reduction notice](https://www.szse.cn/disclosure/notice/general/t20230818_602805.html) | published `2023-08-18`; effective `2023-08-28` | `0.00341%` bilateral | Target candidate; Northbound applicability corroborated by CT/134/23; successor inventory incomplete |
| [SEHK circular CT/134/23](https://www.hkex.com.hk/-/media/HKEX-Market/Services/Circulars-and-Notices/Participant-and-Members-Circulars/SEHK/2023/CT13423B.pdf) | effective `2023-08-28` | handling reduction applies to Northbound | Scope corroboration; not a terminated post-target successor index |
| [NDRC/MOF 发改价格规〔2018〕917号](https://www.ndrc.gov.cn/xxgk/zcfb/ghxwj/201806/t20180627_960950.html) | document `2018-06-22`; effective `2018-01-01` | `0.002%` on stock turnover; prior 2016 authority superseded | Target candidate; later validity/adjustment index and XSHE investor-collection closure incomplete |
| ChinaClear transfer predecessor | before `2022-04-29` | `0.002%` bilateral | Before target |
| [ChinaClear 2022 transfer reduction](https://www.chinaclear.cn/zdjs/gszb/202204/837e3c5031104aa099d6597ba381342a.shtml) | published `2022-04-28`; effective `2022-04-29` | `0.001%` bilateral | Target candidate; Stock Connect applicability corroborated by HKSCC circular; successor inventory incomplete |
| [HKSCC 2022 Northbound transfer circular](https://www.hkex.com.hk/-/media/HKEX-Market/Services/Circulars-and-Notices/Participant-and-Members-Circulars/HKSCC/2022/ce_HKSCC_SET_017_2022_.pdf) | effective `2022-04-29` | Northbound ChinaClear transfer changed `0.002%` to `0.001%` | Target candidate corroboration; distinct from the additional HKSCC fee |
| [HKSCC Operational Procedures section 21](https://www.hkex.com.hk/-/media/HKEX-Market/Services/Rules-and-Forms-and-Fees/Rules/HKSCC/Operational-Procedures/SEC21.pdf) | current displayed rule; introduction traced to 2015 materials | additional `0.002%` gross-value transfer fee per China Connect trade | **Target-affecting access-specific candidate and decisive blocker**; complete amendment chain through cutoff not frozen |
| [Stamp Tax Law](https://fgk.chinatax.gov.cn/zcfgk/c100009/c5193058/content.html) | effective `2022-07-01` | statutory `0.1%`, transaction amount, transferor only | Base target candidate; exact selected representation and full successor index not frozen |
| [MOF/STA Announcement 2023 No. 39](https://fgk.chinatax.gov.cn/zcfgk/c102416/c5211343/content.html) | published `2023-08-27`; effective `2023-08-28` | half collection, yielding `0.05%` seller-only | Target candidate; Northbound applicability corroborated by HKSCC 039/2023; correction/repeal index incomplete |
| [HKSCC circular CD/OES/CCASS/039/2023](https://www.hkex.com.hk/-/media/HKEX-Market/Services/Circulars-and-Notices/Participant-and-Members-Circulars/HKSCC/2023/ce_HKSCC_SET_039_2023.pdf) | effective `2023-08-28` | `0.05%` seller-side stamp duty applies to Northbound | Scope corroboration; not complete successor closure |
| Investor Compensation Levy suspension | suspension from `2005-12-19`; Northbound regime from `2020-01-01` | collection currently zero; reinstatement by SFC announcement | Candidate no-charge state; reinstatement/successor channel unresolved |
| HKSCC portfolio fee schedule | current schedule | tiered annual holding-based cost | Northbound-specific, non-notional, and unrepresentable by current Band model |
| HKSCC settlement/instruction schedules | current schedule | fixed or instruction/participant-based charges | Do not fold into execution notional rates; policy scope decision required |
| [SZSE January-2026 fee table](https://www.szse.cn/marketServices/deal/payFees/index.html) — ordinary A share | page labels its table `2026年1月` | handling `0.0341‰`, regulatory `0.02‰`, transfer `0.01‰`, stamp `0.5‰` | Useful near-target ordinary-A-share endpoint candidate; mutable and before target end, not a terminated historical register |
| [SZSE January-2026 fee table](https://www.szse.cn/marketServices/deal/payFees/index.html) — preferred stock | same mutable page | preferred-stock handling during the pilot is 80% of ordinary-stock standard; derived `0.02728‰` from displayed `0.0341‰`, bilateral | **Product-scope mismatch candidate**; other preferred-stock components and successor chain are not reclosed here |
| [HKEX Northbound transaction page](https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Fees/Securities-(Stock-Connect)/Trading/Transactions?sc_lang=en) — listed ETF column | current displayed table | handling `0.004%` for each purchase or sale; securities-management fee, ChinaClear transfer fee, and stamp duty waived | **Product-scope mismatch candidate**; current mutable display is not complete historical/successor closure and does not waive the separate HKSCC section 21 fee |
| [SZSE Trading Rules 2026 notice](https://www.szse.cn/lawrules/rule/allrules/bussiness/t20260424_620190.html) and [PDF](https://docs.static.szse.cn/www/lawrules/rule/trade/current/W020260424690713155663.pdf) | effective `2026-07-06`; replaces 2023 rules | chapter 9 delegates fees to applicable provisions | Target-start rule disposition only; does not freeze fee economics through target end |

## Separate successor-closure limitation

Even if the route and product-class mismatches were resolved, F1 would remain blocked on evidence closure. No authority-complete, explicitly terminated candidate inventory through a post-target `official_record_as_of` was frozen for all relevant channels and product classes:

- SZSE notices, fee-table versions, corrections, and validity/repeal registers;
- ChinaClear national and Shenzhen notices, tables, corrections, and successor channels;
- NDRC/MOF/CSRC controlling regulatory-fee validity/adjustment records plus XSHE bilateral investor-collection applicability;
- STA/MOF statutory, half-collection, correction, repeal, and successor records;
- SEHK Chapter 14B amendments and Northbound fee circulars;
- HKSCC General Rules/Operational Procedures section 21 amendments, fee circulars, and schedules;
- SFC/HKEX Investor Compensation Levy reinstatement or termination announcements.

Current pages, equal later rates, search results, and unsuccessful searches do not prove complete pagination/range termination or absence of a short-lived, corrected, retroactive, or later-recorded target-affecting act. No gap-free terminal documentary chain and economic chain was reconstructed through an explicit cutoff satisfying:

```text
target_to_exclusive <= official_record_as_of <= closure_evidence_available_at
```

## Source access and byte-evidence limits

| Source class | Access observed | Permitted claim | Limit |
| --- | --- | --- | --- |
| HKEX/HKSCC pages and PDFs | The underlying research handoff records direct fetch as blocked by TUN/fake-IP SSRF protection and therefore relied on indexed first-party-domain content. During repository-report validation, the listed URLs returned HTTP `200`; current raw HTML/PDF responses were saved only under temporary validation storage and inspected through text extraction. | First-party URLs and the displayed/current source facts listed above, including the separate ETF column and section 21 wording | Temporary representations are not committed closure evidence. No source-specific headers, redirect receipt, retrieval receipt, selected-representation hash, or historical-version proof is frozen; current retrieval does not prove retrospective state or complete successor closure |
| SZSE pages/PDF | Listed URLs returned HTTP `200` during report validation; current raw fee-page HTML was saved only under temporary validation storage and extracted as readable text | First-party candidate endpoint facts, including ordinary handling `0.0341‰` bilateral and preferred handling at 80% of ordinary standard | Temporary current HTML is not committed closure evidence and has no source-specific receipt/hash; the mutable January-2026 table predates target end |
| ChinaClear page | Listed URL returned HTTP `200` during report validation | First-party transition URL and candidate rate | No exact selected bytes, correction chain, or terminated successor index is frozen |
| NDRC page | `HEAD` returned `405`; `GET` returned the official page during validation | First-party controlling-authority URL and candidate rate/effective date | Method-specific reachability is not a byte receipt or validity-index closure |
| STA policy-library pages | Listed URLs returned HTTP `200` during report validation | First-party statutory and half-collection URLs and candidate facts | Exact selected representations and complete correction/repeal/successor indexes are not frozen |

The temporary validation retrievals are not repository evidence artifacts. No SHA-256 value in prior research is promoted here to a verified official-byte hash. Prior source hashes remain inherited identifier claims unless their exact official representations and acquisition receipts are independently captured and reviewed.

## Contract options

F1 can proceed only after an explicit contract decision. The acceptable options are:

1. **Add an execution-enforced route-and-product discriminator and separate v2 RuleBooks/economics.** Bind both selected access route and fee product class from immutable profile/order context into fee evaluation. The minimum explicit product classes are ordinary A share, preferred stock, ETF, and every other supported class with distinct official economics. Runtime must reject missing or inconsistent route/product context; metadata, symbol parsing, or documentation alone is insufficient.
2. **Separately approve a narrower enforceable ordinary-A-share-only contract.** Define a new additive contract whose execution path proves both the permitted access route and ordinary-A-share product class, and rejects Northbound or non-ordinary products outside the approved scope before fee evaluation. It must not be achieved by treating the present route/product-blind query as implicitly domestic or ordinary A share.
3. **Separately redesign non-notional participant-cost policy if full route cost is promised.** After route/product execution fees are correctly discriminated, represent portfolio/instruction/settlement costs using their actual participant/state/message bases rather than blending them into trade notional. This does not replace the route/product discriminator.
4. **Remain blocked.** Preserve the existing `COVERAGE_GAP / market_fees` result and do not emit closure, projection, publication, or qualification artifacts.

**Recommendation:** remain blocked under the current contract. For the full envelope, approve option 1 before renewed closure acquisition. If the intended product is narrower, option 2 requires separate approval and execution enforcement. Silently excluding Stock Connect, preferred stock, ETFs, or other supported product classes—and silently generalizing ordinary A-share rates—is not an option.

## Repository disposition and nonclaims

This report alone is the repository change. It creates no closure JSON/body/hash, source receipt, projector, Runtime/profile composer, RuleBook/Band, code, test fixture, declaration, event, publication, manifest, shared registry, or acceptance qualification.

It does not claim provider authority, provider completeness, rule coverage, decision grade, live use, deployment authorization, broker-account parity, verified official bytes, or complete July-2026 successor closure.

## Conclusion

**BLOCKED.** The additional Northbound-only HKSCC `0.002%` (`0.02‰`) gross-trade-value transfer fee makes one route-blind `CnAShareMarketFeeRuleBook` economically false. Preferred-stock handling at 80% of ordinary handling and the distinct Northbound ETF handling/waiver schedule independently make one product-blind RuleBook false. Access route alone is insufficient; valid v2 evaluation must bind both route and fee product class, or a separately approved contract must enforce an ordinary-A-share-only scope. Non-notional participant costs and incomplete successor-index closure remain additional, separate limitations. No G12H F1 success artifact or qualification follows from this report.
