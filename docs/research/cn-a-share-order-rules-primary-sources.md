# China A-share Historical Order Rules and Price Limits Primary Sources

## Scope

This note records the official market facts used to freeze G08D. G08D covers deterministic cash-auction order-rule resolution for XSHG/XSHG STAR and XSHE/ChiNext, including historical effective intervals, daily price limits, order-quantity caps, suspension classification, conservative bar-open limit liquidity, and authoritative residual-sell evidence.

It does not cover fees, tax, corporate actions, Stock Connect, margin trading, B shares, funds, bonds, after-hours trading, live adapters, provider selection, or deployment authorization.

## Official exchange rules

### Shanghai Stock Exchange

SSE《上海证券交易所交易规则（2023年修订）》（上证发〔2023〕32号） establishes:

- Rule 3.3.8: auction buys are 100 shares or an integer multiple; a remaining balance below 100 shares must be sold in one declaration.
- Rule 3.3.9: the general single-order maximum is 1,000,000 shares.
- Rule 3.3.11: the RMB A-share minimum price movement is CNY 0.01.
- Rules 3.3.13 and 3.3.17: the ordinary daily limit is 10%; limits are previous close multiplied by `1 ± ratio`, rounded half-up to the minimum price movement, with the one-tick floor safeguards stated by the rule.
- Rule 3.3.13: the first five trading days after an IPO, the first delisting-board day, and the first relisting day have no daily price limit.
- Rules 4.2.3–4.2.8: suspension and resumption are exchange-announced instrument states; orders may be accepted during some intraday suspensions, but matching is suspended.
- Rules 4.4.10–4.4.12: Main Board risk-warning shares use a 5% daily limit and have a separate investor-level cumulative buy cap. The latter is not a single-order cap and is outside G08D v1.
- Rules 6.1.6–6.1.8: STAR shares use a 20% daily limit; the first five IPO trading days have no daily limit; limit orders are 200–100,000 shares, market orders are 200–50,000 shares, and a remaining balance below 200 shares must be sold once.

Sources:

- Archived release page: <https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/c_20250612_10824490.shtml>
- 2023 rule attachment: <https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/10824490/files/dcbe58edb194451d93f19b1f7dd8fb4c.docx>
- Attachment SHA-256: `7aa2319f6dcf597be1e86b3b69d7c2ad0e6acb2a5d0cc6be48a01af602fded40`
- 2019 STAR rule release: <https://www.sse.com.cn/lawandrules/sselawsrules2025/repeal/rules/c/c_20190301_10785118.shtml>
- Main-board registration implementation date evidence: <https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20230404_5719112.shtml>
- Residual-order front-control clarification: <https://www.sse.com.cn/lawandrules/guide/stock/jyglywznylc/tz/c/c_20230209_5716007.shtml>

The 2023 rules became effective when the first registration-based Main Board shares listed. The official arrangement fixed that date as 2023-04-10.

### Shenzhen Stock Exchange

SZSE《深圳证券交易所交易规则（2023年修订）》（深证上〔2023〕98号） establishes:

- Rule 3.3.8: auction buys are 100 shares or an integer multiple; a remaining balance below 100 shares must be sold in one declaration.
- Rule 3.3.9: the general single-order maximum is 1,000,000 shares; ChiNext limit-order and market-order maxima are 300,000 and 150,000 shares respectively.
- Rule 3.3.11: the RMB A-share minimum price movement is CNY 0.01.
- Rules 3.3.13–3.3.19: Main Board uses a 10% daily limit and ChiNext uses 20%; limits use previous close and half-up rounding to the price tick with the stated one-tick floor safeguards.
- Rule 3.3.15: the first five IPO trading days, the first relisting day, and the first delisting-board day have no daily price limit.
- Rules 4.3.3–4.3.8: suspension/resumption is an explicit instrument state and must not be inferred from an absent bar.
- Chapter 6: Main Board risk-warning shares use 5%; ChiNext risk-warning and delisting-board shares retain 20%, except the no-limit first delisting-board day.

Sources:

- Archived release page: <https://www.szse.cn/lawrules/rule/repeal/rules/t20230217_598773.html>
- 2023 rule attachment: <https://docs.static.szse.cn/www/lawrules/rule/repeal/rules/W020230217564423808793.pdf>
- Attachment SHA-256: `7018114a6e11deb239c2a72e71e49defc6e8841b3e2c093b3bbf809282c67222`
- Main-board registration implementation date evidence: <https://www.szse.cn/aboutus/trends/news/t20230404_599697.html>

The 2023 rules became effective on 2023-04-10, when the first registration-based Main Board shares listed.

### ChiNext historical transition

SZSE《深圳证券交易所创业板交易特别规定》（深证上〔2020〕515号） became effective on the listing day of the first registration-based ChiNext shares. Official SZSE materials identify 2020-08-24 as that listing day and state that existing non-registration ChiNext shares changed synchronously from the former 10% limit to 20%.

Sources:

- 2020 release notice: <https://www.szse.cn/disclosure/notice/general/t20200612_578381.html>
- Official effective-date Q&A: <https://investor.szse.cn/knowledge/stock/chinext/t20200729_580055.html>
- Official price-limit Q&A: <https://investor.szse.cn/knowledge/stock/chinext/t20200729_580056.html>
- First registration-based ChiNext listing announcement: <https://www.szse.cn/aboutus/trends/news/t20200814_580660.html>
- First 18 listings report: <https://www.szse.cn/aboutus/trends/news/t20200824_580949.html>

G08D therefore freezes a standard-seasoned ChiNext transition from 10% through 2020-08-23 to 20% from 2020-08-24. It does not extrapolate unverified historical risk-warning or IPO classifications across that boundary.

## Canonical distinction between facts and evidence

Exchange-rule facts:

- board-specific ratio, tick, minimum/order-lot rule, and execution-style maximum;
- no-limit listing phases;
- suspension means matching is not occurring even when some order entry/cancellation may remain possible;
- the complete residual component may not be split across declarations.

Instrument/listing/status evidence supplied by the MarketBundle or caller:

- board classification;
- risk-warning or delisting classification;
- IPO/relisting/delisting trading-day phase;
- previous close/reference price;
- per-instant suspended, resumed, or normal status;
- authoritative account position, sellable balance, reservations, and working orders.

G08D does not infer these facts from symbol prefixes, missing bars, zero volume, current exchange rules, or wall-clock/network reads.

## G08D system conventions

- Rule coverage is finite and immutable. Missing or overlapping intervals fail closed; current rules are never used as fallback for historical instants.
- A known no-session G08A result is `NO_TRADE`, not suspension and not missing data.
- Missing session, status, previous-close, classification, or interval evidence is `DATA_MISSING`/structured component failure.
- For bar-open simulation, an upper-limit open blocks a BUY and a lower-limit open blocks a SELL unless a future queue-capable model supplies stronger contemporaneous evidence. The opposite direction continues. Full-day volume is never used to infer queue execution.
- The bar-open rule is a conservative Simulation Profile convention, not an exchange claim that every order at a limit price is unfillable.
- Ordinary Main Board quantity-lattice identity must match the G08C lattice. STAR and ChiNext use their own board-specific effective snapshots; G08C remains ordinary-Main-Board only.
- An odd residual SELL can be approved only from exact evaluated-at portfolio, availability, reservation, and working-order evidence. Static `PositionEffect.CLOSE`, target quantity, or sizing evidence is insufficient.
