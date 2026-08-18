# G12H XSHE July-2026 Fee/Tax Authority Primary Sources

## Status

**BLOCKED — fail closed.**

Official primary sources identify candidate rates for ordinary domestic CNY A-share cash-auction executions on XSHE:

- transaction handling fee: `0.0341‰` of transaction amount, buyer and seller;
- securities-business regulatory fee: `0.02‰` of transaction amount, bilateral investor collection as displayed by SZSE;
- stock transaction transfer fee: `0.01‰` of transaction amount, buyer and seller;
- securities transaction stamp duty: `0.5‰` of transaction amount, seller/transferor only.

Those sources do **not** prove a finite, full-target continuity and revision-closure chain. The immutable target extends beyond the analysis instant, and every candidate rule is open-ended. Applying any candidate to the post-analysis segment would infer that no later publication changed the rule before target end. G12H forbids that inference.

No July-2026 fee/tax authority set is produced. No code, fixture, registry, shared Acceptance Matrix, plan README, or existing authority artifact is changed.

## Scope and nonclaims

This report evaluates only the missing G12H `market_fees` and `stamp_duty` prerequisite for standard domestic CNY A-share cash-auction trading on XSHE Main Board. It preserves candidate authority facts without qualifying them for the immutable target.

This report does **not** claim:

- provider authority, provider completeness, or provider parity;
- decision-grade, live-trading, deployment, broker-account, or statement-parity qualification;
- a universal broker commission, minimum commission, bundled-fee convention, or rebate;
- block-trade, after-hours fixed-price, B-share, fund, bond, Stock Connect, margin/short, or non-CNY coverage;
- official per-fill rounding, broker rounding, or application quantization conventions;
- corporate-action tax, VAT, financing interest, or transfer-tax exemption coverage;
- that a current page, later equal-rate table, or unsuccessful repeal search proves historical continuity;
- any modification of the PASSED G08H/G12C/D artifacts or authorization to implement G12H.

## Local evidence actually reviewed

The earlier research handoff incorrectly reported that the G12H blocker, order/quantity material, and task analysis could not be found. They are present at these repository paths and were reviewed:

| Local input | Actual path | File SHA-256 |
| --- | --- | --- |
| G12H five-dimension blocker | `docs/research/g12h-five-dimension-target-coverage-blocker-v1.md` | `400566f6737a614201dc2068d659133035314bbe6e45bdd7ce4e05405fb77f3d` |
| G12H readiness/task analysis | `docs/research/g12h-rule-coverage.md` | `6409348ee3bd05c157902633f940960a7baea0dc72ce5721895f4e0386922bc1` |
| Existing fee/tax source note | `docs/research/cn-a-share-commission-tax-primary-sources.md` | `6085926639a142ae65b00757c044e9c71934419f0ba46652d13a0bb0ca28abaf` |
| Order-rule source note | `docs/research/cn-a-share-order-rules-primary-sources.md` | `d50b3179f7d6354ea23da9cd6837853b841ff929a5ea1b5a606d7a89889fd215` |
| Quantity-lattice source note | `docs/research/cn-a-share-quantity-lattice-primary-sources.md` | `27cccf06d6b6f9d908657927209c4b59ef24fad19419240bfe3455c3e4011010` |
| Corporate-action source note | `docs/research/cn-a-share-corporate-actions-primary-sources.md` | `79b6d7ef63347eb45c6b5391dd4f1349cdd67a4247721f3963cffa5984037ed6` |
| G12H plan | `docs/implementation/plans/g12/g12h.md` | `50b4744bdbcebf28c15a8c683b7fe20176c0d1d2da797125f036a38b9bfb203c` |
| G12H blocker test | `tests/bundle_builder/rule_authorities/test_g12h_rule_coverage_blocker.py` | `1a2a8f8a7347604ec7223d2eddadefdcb338cd62df4623315969bf6b9e710fa6` |
| G12H declaration fixture | `tests/fixtures/market_data/rule_authorities/cn-a-share-development-v1/declaration.json` | `19017a07fbfd2da954483648fb168d87212f88e92fccca7c28fb0a514b202515` |
| G12H publication fixture | `tests/fixtures/market_data/rule_authorities/cn-a-share-development-v1/publication.expected.json` | `7a95188cf05d401fcaed80b548f82f22f0b9bc23f6423c6ff1190de775291f7d` |

The declaration's canonical hash is `sha256:6e0c60a75e957467a5cfe1b4e2bbbb786c463747ae96adf059c54ecef4a1b7b6`; the publication manifest hash is `sha256:d85f6a85f7977a2096d1a26fe33a3892640bd27dc28e49b3e6b379650ab984c8`. The immutable publication source is commit `832f53a74d3f74436ecae8672bd1c0dd3530c814`.

`/tmp/g12h-aligned-authority-options.md` was also present. Its surviving content confirms the blocker path, blocker hash, declaration byte/canonical hashes, and publication byte hash, but the file is truncated after six lines in a serialized child-run result. It is not a complete independent oracle report. Its usable interval-inventory conclusion agrees with the repository evidence: Calendar, XSHE Main Board order rules, and XSHE corporate-action entitlements exact-cover the target; the fee/tax bands end in August 2023; the five-dimension intersection is empty; and finite bands must not be extrapolated.

## Immutable target and analysis boundary

The declaration fixes:

| Boundary | UTC | Asia/Shanghai |
| --- | --- | --- |
| Target start, inclusive | `2026-07-05T16:00:00Z` | `2026-07-06 00:00:00+08:00` |
| Analysis/availability instant | `2026-07-20T10:00:00Z` | `2026-07-20 18:00:00+08:00` |
| Target end, exclusive | `2026-07-30T16:00:00Z` | `2026-07-31 00:00:00+08:00` |
| Post-analysis target segment | `[2026-07-20T10:00:00Z, 2026-07-30T16:00:00Z)` | `[2026-07-20 18:00, 2026-07-31 00:00)` |

The post-analysis segment is `10 days 6 hours`. A component can pass only if official authority available no later than the analysis instant establishes the exact rate, basis, side, venue/mechanism, and a complete effective/repeal/correction/supersession chain for every target instant. An open-ended rule does not itself close a future interval.

The existing declaration deliberately records `provider_authority_qualified=false`, `revision_closure_complete=false`, `rule_coverage_qualified=false`, `decision_grade_eligible=false`, and `deployment_authorized=false`.

## Candidate authority findings

### 1. XSHE transaction handling fee

**Candidate fact:** `0.0341‰` of transaction amount, charged bilaterally for ordinary A-share transactions. The prior `0.0487‰` bilateral rate changed effective `2023-08-28`.

- Primary transition authority: 深圳证券交易所《关于下调股票交易经手费收费标准的通知》.
- Publication date: `2023-08-18`.
- Effective date: `2023-08-28`.
- Official notice: <https://www.szse.cn/disclosure/notice/general/t20230818_602805.html>.
- Official investor-facing fee table: <https://www.szse.cn/marketServices/deal/payFees/> (the research capture also used <https://www.szse.cn/marketServices/deal/payFees/index.html>).
- Collection mechanism: 深圳证券交易所业务收费管理办法, article 8, <http://docs.static.szse.cn/www/marketServices/deal/payFees/W020200228805325484325.pdf>, stating that ChinaClear Shenzhen branch collects the handling fee on behalf of SZSE.
- Scope limit: the SZSE material separately addresses discounted block trades; this report retains only standard cash-auction A-share trading and does not apply the auction rate to block trading.
- Stated sunset/repeal: none in the located notice.
- As-published interval: `[2023-08-28, unknown supersession)`.

Local source identities preserved by the existing note/research handoff:

- transition notice: `szse.transaction-handling.2023-08-18`, `sha256:6645a32b6ab297741f22e6b8e959342bb4c9312757d0f1d99de37a0a410d12ba`;
- dynamic fee-page snapshot: `szse.market-fee-collection.2026-08-08-snapshot`, `sha256:fbd7df3dfa07778b1318564563d22992f19d06bde415144fef248f27674f03c7`.

**Closure result: failed.** The notice identifies the candidate transition, and the dynamic page is labeled January 2026, but no pre-analysis finite authority fixes the rate through `2026-07-31 00:00+08:00`. The dynamic page can be revised and the locally hashed bytes were retrieved after analysis.

### 2. Securities-business regulatory fee

**Candidate fact:** `0.02‰` of stock transaction amount. NDRC/MOF sets the authority-level charge on the Shanghai and Shenzhen exchanges; the SZSE fee table displays bilateral investor collection on behalf of CSRC.

- Primary authority: 国家发展改革委、财政部《关于证券期货业监管费标准等有关问题的通知》, 发改价格规〔2018〕917号.
- Document date: `2018-06-22`; official page path/publication date: `2018-06-27`.
- Effective date: `2018-01-01`.
- Official page: <https://www.ndrc.gov.cn/xxgk/zcfb/ghxwj/201806/t20180627_960950.html>.
- Supersession: expressly repeals 发改价格〔2016〕14号 for the securities/futures business regulatory-fee standard.
- Later context: 发改价格〔2021〕1947号 extends the standard to Beijing and states that standards may be evaluated and adjusted: <https://www.ndrc.gov.cn/xxgk/zcfb/tz/202201/t20220107_1311590.html> (alternate official rendering preserved by the research handoff: <https://www.ndrc.gov.cn/xxgk/zcfb/tz/202201/t20220107_1311590_ext.html>).
- Bilateral investor collection: SZSE fee table, <https://www.szse.cn/marketServices/deal/payFees/>.
- Ownership distinction: 917 alone does not establish bilateral investor pass-through; that fact comes from the SZSE table.
- As-published interval: `[2018-01-01, unknown supersession)`.

Local source identities:

- NDRC/MOF 917 page: `ndrc.securities-business-regulatory-fee.2018-917`, `sha256:4c8c8426c7cc797a99a86f8d8bea21fef8f1a944d1ef14857286c9784085b3c8`;
- SZSE dynamic fee-page snapshot: `szse.market-fee-collection.2026-08-08-snapshot`, `sha256:fbd7df3dfa07778b1318564563d22992f19d06bde415144fef248f27674f03c7`.

**Closure result: failed.** The rate, basis, venue, and displayed investor-side collection are identified, but no finite pre-analysis authority or complete effective/invalidated register snapshot proves no adjustment through target end.

### 3. ChinaClear stock transaction transfer fee

**Candidate fact:** `0.01‰` of transaction amount, charged to buyer and seller for Shanghai and Shenzhen A shares. The prior unified `0.02‰` bilateral rate was reduced by 50%.

- Primary authority: 中国结算《关于降低股票交易过户费收费标准的通知》.
- Publication date: `2022-04-28`.
- Effective date: `2022-04-29`.
- Official notice: <https://www.chinaclear.cn/zdjs/gszb/202204/837e3c5031104aa099d6597ba381342a.shtml>.
- Official Shenzhen corroborating table: <https://www.chinaclear.cn/zdjs/fbzyls/202512/a59388fbfa714c5fa546784891a42e30/files/%E6%B7%B1%E5%9C%B3%E5%B8%82%E5%9C%BA%E8%AF%81%E5%88%B8%E7%99%BB%E8%AE%B0%E7%BB%93%E7%AE%97%E4%B8%9A%E5%8A%A1%E6%94%B6%E8%B4%B9%E5%8F%8A%E4%BB%A3%E6%94%B6%E7%A8%8E%E8%B4%B9%E4%B8%80%E8%A7%88%E8%A1%A8.pdf>.
- As-published interval: `[2022-04-29, unknown supersession)`.

Local source identities:

- transition notice: `chinaclear.stock-transfer-fee.2022-04-28`, `sha256:68763b8fe13f7fb90f378b077033b692aafc4eca851c78c18a306b001d591a60`;
- Shenzhen table: `sha256:dff4a06ce20e180f4a85ddae138211dcf7dd3246fb84775453cfd21cbaec6573`.

**Closure result: failed.** The 2022 notice identifies rate, basis, side, venues, and effective date. The December-2025 table corroborates the same candidate, but an equal later table and absence of a found adjustment do not establish complete continuity, especially for the post-analysis target segment.

### 4. Seller-side securities transaction stamp duty

**Candidate fact:** `0.5‰` (`0.05%`) of transaction amount, seller/transferor only.

The primary legal chain is:

1. 《中华人民共和国印花税法》 defines securities trading, taxes the transferor rather than the transferee, uses transaction amount as the basis, names the securities registration and clearing institution as withholding agent, and sets the securities-transaction schedule rate at `1‰`.
   - Passed/promulgated: `2021-06-10`.
   - Effective: `2022-07-01`.
   - Official STA policy-library page: <https://fgk.chinatax.gov.cn/zcfgk/c100009/c5193058/content.html>.
2. 财政部、税务总局《关于减半征收证券交易印花税的公告》, 财政部 税务总局公告2023年第39号, applies half collection from `2023-08-28`, yielding `1‰ × 1/2 = 0.5‰`.
   - Published: `2023-08-27`.
   - Effective: `2023-08-28`.
   - Official STA policy-library page: <https://fgk.chinatax.gov.cn/zcfgk/c102416/c5211343/content.html>.
   - Official China Government policy page retained by the local source note: <https://www.gov.cn/zhengce/zhengceku/202308/content_6900443.htm>.

The existing G08E fixture also binds the prior sell-only baseline through the official STA 12366 answer quoting 财税明电〔2008〕2号: <https://12366.chinatax.gov.cn/nszx/onlinemessage/detail?id=c012f7a11b0e48429e85e861b2682d3e>.

Local source identities:

- sell-only `1‰` baseline quotation: `sta.12366.stamp-duty.2008-2-quotation`, `sha256:69179c93a4861d2fad5d96d2d8e85b3346e0b70ac8213129959bcb4fa5d3f6ba`;
- 2023 half-collection source identity: `mof-sta.stamp-duty.2023-39`, `sha256:970711682948365c3f79afc476df67d5f2d29f57ed239f695f1308f45acffdaf`.

The local notes do not preserve a byte hash for the Stamp Tax Law policy-library page itself. The law and half-collection rule are open-ended: law `[2022-07-01, unknown legislative supersession)` and half collection `[2023-08-28, unknown supersession)`.

**Closure result: failed.** The legal basis, calculation basis, side, withholding mechanism, base rate, reduction, and resulting candidate rate are identified. No pre-analysis artifact prevents a later law, announcement, correction, or effective-date change from affecting the target's post-analysis segment.

## Informational candidate matrix — not qualified

| Component | Candidate rate | Basis | Side | Scope/mechanism | Published/effective | Finite full-target authority? |
| --- | ---: | --- | --- | --- | --- | --- |
| Transaction handling fee | `0.0341‰` | transaction amount | buyer and seller | XSHE ordinary A-share; ChinaClear Shenzhen collects for SZSE | published `2023-08-18`; effective `2023-08-28` | **No** |
| Securities-business regulatory fee | `0.02‰` | stock transaction amount | bilateral investor collection shown by SZSE | XSHE; collected for CSRC | document `2018-06-22`; effective `2018-01-01` | **No** |
| Transaction transfer fee | `0.01‰` | transaction amount | buyer and seller | ChinaClear; Shenzhen A share | published `2022-04-28`; effective `2022-04-29` | **No** |
| Securities transaction stamp duty | `0.5‰` | transaction amount | seller/transferor only | ChinaClear is statutory withholding agent | law effective `2022-07-01`; halving published `2023-08-27`, effective `2023-08-28` | **No** |

These values must not be installed as a qualified G12H July-2026 rule band.

## Static, dynamic, and retrieval limitations

The official-source byte hashes above were preserved by the existing local fee/tax note and the completed research handoff. The local note records retrieval on `2026-08-08` UTC, after the `2026-07-20T10:00:00Z` analysis instant. Those hashes identify later-retrieved bytes; they do not prove that mutable content was publicly available in the same form by the analysis instant.

| Evidence | Form | Recorded access | Limitation |
| --- | --- | --- | --- |
| NDRC/MOF 2018 rule | Static authority page | Readable text and local hash | Open-ended; no authority-complete invalidation snapshot through target end |
| Stamp Tax Law / Announcement 39 | Static policy-library pages | Readable text; Announcement 39 hash preserved | Law-page bytes/attachment hash not preserved locally; both rules remain amendable |
| SZSE 2023 handling notice | JS-rendered authority page | Official URL and post-analysis local hash | No pre-analysis exact-byte capture or signed historical version |
| SZSE January-2026 fee table | Dynamic current page | Extracted and post-analysis local hash | Mutable display; no as-of-analysis version, headers, or revision history |
| ChinaClear 2022 transfer notice | Authority page | Official URL and post-analysis local hash | Direct extraction was incomplete in the research run; no complete as-of register |
| ChinaClear Shenzhen table | Static PDF | Official URL and post-analysis local hash | Later/equal table corroborates a candidate but cannot prove uninterrupted continuity |
| SZSE/ChinaClear lists and repeal searches | Dynamic/search interfaces | Partly discoverable | Search absence is not an authority-issued completeness certificate |

The research run recorded JavaScript rendering and incomplete extraction, not a robots-denial response. It did not preserve raw response headers, redirect chains, content encodings, a trustworthy transport timestamp for every fetch, or an authority-signed historical snapshot as of the analysis instant.

## Effective/repeal/revision conclusion

The official materials establish explicit predecessor transitions:

- handling fee `0.0487‰ → 0.0341‰` effective `2023-08-28`;
- regulatory-fee 2016 notice repealed by the 2018 notice;
- transfer fee `0.02‰ → 0.01‰` effective `2022-04-29`;
- stamp duty statutory `1‰`, seller-only baseline, with half collection to `0.5‰` effective `2023-08-28`.

They do not establish a finite end boundary or an authority-complete revision closure through `2026-07-31 00:00+08:00`. Dynamic/current pages can change; later captures cannot prove their prior state; and a search that finds no repeal cannot prove that all correction, supersession, invalidation, or later-effective publications are absent.

Most importantly, no post hoc acquisition can make a result-affecting fact first published after `2026-07-20T10:00:00Z` available at that analysis instant. Under the immutable target and analysis boundary, open-ended rules cannot cover the post-analysis segment without inferring no change.

## Exact next acquisition artifacts

A fresh current-page capture is insufficient. The prerequisite requires all of the following, additively and without modifying PASSED artifacts:

1. **Post-target authority-complete closure packages** covering publications through at least `2026-07-31 00:00+08:00` for:
   - SZSE fee standards and all handling-fee adjustment, correction, repeal, and invalidation notices;
   - ChinaClear Shenzhen fee tables and all stock-transfer-fee adjustment, correction, repeal, and invalidation notices;
   - NDRC/MOF/CSRC effective and invalidated document registers for 发改价格规〔2018〕917号 and successors;
   - MOF/STA effective and invalidated policy registers for the Stamp Tax Law, Announcement 2023 No. 39, and successors.
2. **Authority-signed or authority-generated historical snapshots as of `2026-07-20T10:00:00Z`** for each register and dynamic fee table, including revision history rather than a fresh HTML page.
3. **Original immutable bytes and provenance** for every retained document and attachment: cryptographic hash, official publication metadata, first-publication timestamp, retrieval UTC timestamp, HTTP status/headers, redirects, content encoding, and capture method.
4. **A closed revision/supersession set** proving that no omitted correction, cancellation, repeal, replacement, or retroactively effective publication affects any target instant.
5. **A new additive five-dimension declaration and G12C/D publication** only after the fee/tax evidence meets the same finite target as Calendar, XSHE Main Board order rules, and XSHE corporate-action entitlements.

Even those artifacts cannot satisfy a strict “all result-affecting facts available by analysis” requirement if a relevant publication first appears after the analysis instant. To remove that structural conflict, a separately authorized task would have to move the analysis instant to or after target end, or shorten the target to end no later than the analysis instant. This report does neither.

## Repository disposition

- No authority set was created.
- No code, test, fixture, registry, shared Acceptance Matrix, or plan README was changed.
- Existing G08H and G12C/D bytes remain untouched.
- No merge or push is authorized or performed by this report.

## Conclusion

**BLOCKED.** Official sources identify plausible July-2026 XSHE fee/tax candidate rates, sides, bases, and mechanisms, but do not prove finite full-target continuity or revision closure. Because the immutable target extends `10 days 6 hours` beyond the analysis instant, qualifying the open-ended rules through target end would infer no change. G12H must remain fail-closed, and no July-2026 authority set may be produced from this evidence.
