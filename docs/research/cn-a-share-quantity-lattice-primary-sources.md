# China A-share Quantity Lattice Primary Sources

## Scope

This note records primary-source facts used by G08C for ordinary RMB A-share cash auction order quantities. It does not cover STAR Market, ChiNext special rules, ETFs, funds, bonds, B shares, Stock Connect, margin trading, after-hours trading, broker UI behaviour, order retry, or fill semantics.

## Exchange rules

### Shanghai Stock Exchange

《上海证券交易所交易规则（2023年修订）》Rule 3.3.8 states:

> 通过竞价交易买入证券的，申报数量应当为100股（份）或其整数倍。卖出证券时，余额不足100股（份）的部分，应当一次性申报卖出。

Sources:

- 2023 release page: <https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/c_20250612_10824490.shtml>
- 2023 rule attachment: <https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/10824490/files/dcbe58edb194451d93f19b1f7dd8fb4c.docx>
- 2026 release page: <https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20260424_10816492.shtml>
- 2026 rule attachment: <https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/10816492/files/704204728fe74fff89de4f16efda4791.docx>

SSE《 关于进一步明确竞价交易申报数量及前端控制有关事项的通知 》（上证函〔2014〕301号）clarifies:

- A holding that is an exact multiple of 100 must be sold in 100-share multiples.
- For a non-multiple holding, the complete sub-100 residual may be sold once by itself or combined with a 100-share multiple; it may not be split.
- From 299 shares, examples allow 99, 100, 199, 200, or 299 shares, and reject quantities that split the 99-share residual such as 1, 101, 198, or 298.

Source: <https://www.sse.com.cn/lawandrules/guide/stock/jyglywznylc/tz/c/c_20230209_5716007.shtml>

### Shenzhen Stock Exchange

《深圳证券交易所交易规则（2023年修订）》Rule 3.3.8 has the same 100-share buy and one-time residual-sale wording. Rule 10.6 defines “不足” as excluding the stated number.

Sources:

- 2023 release page: <https://www.szse.cn/lawrules/rule/repeal/rules/t20230217_598773.html>
- 2023 rule attachment: <https://docs.static.szse.cn/www/lawrules/rule/repeal/rules/W020230217564423808793.pdf>
- 2026 release page: <https://www.szse.cn/lawrules/rule/trade/current/t20260424_620190.html>
- 2026 rule attachment: <https://docs.static.szse.cn/www/lawrules/rule/stock/W020260424690713155663.pdf>
- Main-board investor Q&A: <https://investor.szse.cn/knowledge/stock/deal/t20230308_599142.html>

SZSE’s implementation notice likewise distinguishes normal 100-share multiples from the complete sub-100 residual component and requires member-side front-end quantity controls.

Source: <https://www.szse.cn/lawrules/rule/trade/current/t20150914_565054.html>

## Canonical interpretation for G08C

For the exchange-described non-negative holding balance `H`, normal sell lot `L=100`, and residual `r=H mod L`:

- Buy order quantity must be a positive multiple of 100.
- A sell quantity may be a multiple of 100.
- If `r` is in `1..99`, a sell quantity may additionally contain that complete `r` exactly once, alone or combined with a multiple of 100.
- The residual component cannot be split across orders.
- “One declaration” means one exchange order submission, not one guaranteed fill.
- The rule constrains order quantity relative to authoritative holdings; it is not an absolute target-position lattice.

## Facts not established by these sources

The exchange texts do not define:

- a target-position rounding algorithm;
- `ResidualPositionPolicy`;
- automatic sell-all, rounding, splitting, retries, or broker UI behaviour;
- partial-fill cancellation and re-entry handling;
- which application balance is authoritative after reservations or working orders;
- ordinary-A-share eligibility from the repository’s broad `InstrumentDefinition` alone.

The exchange texts do not define an application’s authoritative sellable balance. G08C maps fixture current Position to the exchange-described holding balance only as an explicit system precondition, excludes working orders and reservations, and defers order-admission and lifecycle evidence to G08D/G08H.

## Historical and product limits

The 2023 and 2026 general exchange rules retain the quoted wording. The 2026 rules state an effective date of 2026-07-06 and repeal the 2023 rules; exact historical intervals remain G08D’s responsibility. The general 100-share statement must not be applied to products with distinct rules; for example, SSE’s separate STAR Market 200-share minimum/residual rule is Rule 6.1.7 in the 2023 edition and Rule 6.7 in the 2026 edition. G08C’s ordinary A-share classification is consequently a caller/G08H precondition, not a fact inferred from symbol text.
