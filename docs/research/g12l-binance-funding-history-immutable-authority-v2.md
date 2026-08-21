# Research: G12L Binance USD-M funding-history joined immutable authority v2

## Summary

**Verdict: NOT CLOSED (blocker).** Binance now publishes checksummed monthly USD-M `fundingRate` archives, but the funding archive is a three-column event series (`calc_time`, `funding_interval_hours`, `last_funding_rate`) rather than the REST funding-history row (`fundingTime`, `fundingRate`, funding-charge-associated `markPrice`). The separate checksummed `markPriceKlines` archive contains interval OHLC bars, and Binance does not specify an authoritative rule equating any bar field to the REST row’s funding-time `markPrice`; joining them would manufacture authority.

No first-party Binance correction/revision artifact was found that closes historical REST funding-history rows. Binance’s own public-data README also says archived files may later be replaced and treats its `updates/` records as the exhaustive replacement log, so a `.CHECKSUM` proves integrity of the currently served ZIP, not permanent immutability of the URL.

## Findings

1. **Blocker — the authoritative REST row is already joined, but it is mutable API output rather than an immutable historical artifact.** Binance documents `GET /fapi/v1/fundingRate` as returning `symbol`, `fundingRate`, `fundingTime`, and `markPrice`, explicitly defining `markPrice` as the “mark price associated with a particular funding fee charge.” The current legacy example also shows `rateType`, increasing the schema gap with the bulk archive. [Binance USD-M Get Funding Rate History](https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History)

2. **Blocker — the official bulk funding archive does not contain funding-time mark price.** The official Public Data index exposes monthly USD-M funding files at `data/futures/um/monthly/fundingRate/<SYMBOL>/<SYMBOL>-fundingRate-YYYY-MM.zip` with adjacent `.CHECKSUM` objects. Inspection evidence for this archive family identifies only `calc_time`, `funding_interval_hours`, and `last_funding_rate`; no `markPrice` field is present. The first-party repository’s current README does not document a richer funding schema or claim equivalence to the REST response. [Official Binance Public Data fundingRate index](https://data.binance.vision/?prefix=data%2Ffutures%2Fum%2Fmonthly%2FfundingRate%2F) [Official Binance Public Data repository](https://github.com/binance/binance-public-data)

3. **Blocker — `markPriceKlines` cannot close the missing REST field without an undocumented join.** Binance documents mark-price klines as OHLC candlesticks “uniquely identified by their open time”; the response contains open/high/low/close and close time for an interval. It does not state that the kline open, close, or any other bar statistic equals the funding-history `markPrice` associated with the charge. Exact funding timestamps may also carry millisecond jitter, so equality to an interval boundary cannot be assumed. [Binance USD-M Mark Price Kline/Candlestick Data](https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/market-data/rest-api/Mark-Price-Kline-Candlestick-Data)

4. **High — current mark price/premium-index output is not a historical correction artifact.** `GET /fapi/v1/premiumIndex` returns a current `markPrice`, response `time`, latest funding rate, and `nextFundingTime`. It does not reconstruct the funding-charge-associated mark price for past funding slots. [Binance USD-M Mark Price](https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/market-data/rest-api/Mark-Price)

5. **High — Binance checksums establish file integrity, not immutable publication.** Binance says every ZIP has a `.CHECKSUM` for SHA-256 verification, but also says archived files “may be updated at a later date” and that the listed update artifacts contain old and replacement checksums. Therefore, closure would require preserving exact ZIP/checksum bytes plus receipt metadata/hash, or a Binance revision artifact identifying the replaced and replacement objects—not merely citing the live URL. [Official Binance Public Data README — CHECKSUM and archive updates](https://github.com/binance/binance-public-data/blob/master/README.md)

6. **Blocker — no first-party funding-history correction/revision artifact was found.** Binance’s official `updates/` tree contains the published archive-update artifacts surfaced by the repository (aggregate-trade and kline updates); no funding-rate or funding-history revision artifact was found. Searches of Binance’s public-data issues and derivative docs likewise found operational fixes for other datasets, but no artifact mapping historical REST funding rows or supplying old/new checksums for funding history. [Official `updates/` tree](https://github.com/binance/binance-public-data/tree/master/updates)

7. **High — an official 2021 request confirms the historical separation rather than a joined archive.** In Binance’s public-data issue #44, a user requested historical funding data while noting interest in mark/index price. Binance replied that mark and index price were already in futures public data, while funding history was separately available from the funding-history page. That first-party record does not assert an authoritative join, and no later first-party schema/correction artifact located in this pass supersedes it. [Binance public-data issue #44](https://github.com/binance/binance-public-data/issues/44)

## Bounded artifact attempts

The following small first-party objects were targeted:

- `https://data.binance.vision/data/futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2024-01.zip.CHECKSUM`
- `https://data.binance.vision/data/futures/um/monthly/markPriceKlines/BTCUSDT/1m/BTCUSDT-1m-2024-01.zip.CHECKSUM`
- Official S3 prefix listing for `data/futures/um/monthly/fundingRate/`
- Official Public Data README and `updates/` index

This child runtime’s fetch layer blocked Binance/S3/GitHub direct retrieval because the configured proxy resolved them into the reserved `198.18.0.0/15` range. Consequently, no exact response headers, receipt timestamp, ETag, checksum bytes, or ZIP hash were captured here. Search results did confirm the official paths and first-party documentation, but **that is not a substitute for byte capture**. The parent should rerun the two bounded checksum/ZIP header captures with `curl --include`/`curl --remote-name` in the repository environment if available.

## Closure test

G12L can close only if first-party evidence supplies one of:

1. A checksummed/captured Binance artifact whose same row contains `fundingTime`, `fundingRate`, and the funding-charge-associated `markPrice`; or
2. A Binance correction/revision artifact that identifies historical REST funding-history values and preserves old/new identity (for example, paths and old/new checksums).

The currently observed combination fails both tests:

- `fundingRate` ZIP: time + interval + rate, no funding-charge mark price.
- `markPriceKlines` ZIP: interval OHLC, no documented equivalence to the REST charge mark.
- `.CHECKSUM`: integrity for a served object, while Binance explicitly permits later replacement.
- `updates/`: no funding-history revision artifact found.

**Do not qualify the registry and do not construct a kline-derived mark-price join.**

## Sources

- Kept: [Binance USD-M Get Funding Rate History](https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/market-data/rest-api/Get-Funding-Rate-History) — first-party schema and semantics for the required joined REST row.
- Kept: [Binance USD-M Mark Price Kline/Candlestick Data](https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/market-data/rest-api/Mark-Price-Kline-Candlestick-Data) — first-party kline semantics showing interval OHLC rather than funding-charge mark price.
- Kept: [Binance USD-M Mark Price](https://developers.binance.com/legacy-docs/derivatives/usds-margined-futures/market-data/rest-api/Mark-Price) — first-party current mark/latest funding/next funding schema.
- Kept: [Binance Public Data README](https://github.com/binance/binance-public-data/blob/master/README.md) — first-party checksum semantics and explicit archive replacement policy.
- Kept: [Binance Public Data updates tree](https://github.com/binance/binance-public-data/tree/master/updates) — first-party published revision-artifact inventory.
- Kept: [Binance public-data issue #44](https://github.com/binance/binance-public-data/issues/44) — first-party historical statement separating funding history from mark/index archives.
- Kept: [Binance Public Data fundingRate index](https://data.binance.vision/?prefix=data%2Ffutures%2Fum%2Fmonthly%2FfundingRate%2F) — official archive namespace.
- Dropped: third-party downloaders, datasets, blogs, wrappers, and CCXT issues — useful corroboration of the three-column archive, but excluded from the verdict because the task requires first-party Binance authority.
- Dropped: Binance Square/community posts — not needed where official developer docs and the official repository exist.

## Gaps

- Exact bytes/headers/ETag/Last-Modified/SHA-256 for a bounded current funding ZIP and checksum could not be captured in this runtime due the proxy/SSRF block.
- The official Public Data README does not presently document the fundingRate archive columns, so byte-level inspection of one recent file remains the best final confirmation that no schema expansion occurred after 2025.
- No repository worktree, Git status, or existing local G12L evidence files were available to this research child; commit creation and validation must be performed by the parent session.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Blocker/high findings are recorded in /tmp/backtest-binance-funding-authority-v2/research.md with concrete official Binance paths and URLs; verdict is NOT CLOSED because no same-row immutable authority or funding-history revision artifact was found."
    }
  ],
  "changedFiles": [
    "/tmp/backtest-binance-funding-authority-v2/research.md"
  ],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "web_search: official Binance fundingRate archive, markPriceKlines, REST funding-history, checksum, and update-artifact queries",
      "result": "passed",
      "summary": "Located first-party Binance docs, Public Data README/index, updates tree, and issue evidence; no funding correction artifact found."
    },
    {
      "command": "fetch_content: bounded official Binance/S3 checksum and ZIP artifacts",
      "result": "failed",
      "summary": "Direct fetch blocked because proxy DNS resolved official hosts into reserved 198.18.0.0/15; no bytes or headers captured."
    },
    {
      "command": "write /tmp/backtest-binance-funding-authority-v2/research.md",
      "result": "passed",
      "summary": "Research brief and structured acceptance report written to the authoritative runtime path."
    }
  ],
  "validationOutput": [
    "First-party REST schema includes fundingRate, fundingTime, and charge-associated markPrice.",
    "Official bulk funding archive evidence remains a separate three-column rate series; mark-price archive is OHLC kline data.",
    "Official README states archives may be replaced and checksums verify integrity, so live URL plus checksum is not permanent immutability.",
    "No official funding-history correction/revision artifact was found in the published updates inventory."
  ],
  "residualRisks": [
    "A very recent fundingRate ZIP schema expansion could only be ruled out conclusively by byte-level inspection of a recent official ZIP; direct retrieval was blocked in this runtime.",
    "No Git worktree validation or commit was possible in this research-child environment."
  ],
  "noStagedFiles": true,
  "diffSummary": "Added one runtime research report only; no registry qualification edits and no repository files changed by this child.",
  "reviewFindings": [
    "blocker: Binance fundingRate bulk archive does not provide the REST funding-charge-associated markPrice in the same row.",
    "blocker: No documented authoritative mapping from markPriceKlines OHLC to REST funding-history markPrice.",
    "blocker: No first-party funding-history correction/revision artifact found.",
    "high: Binance explicitly permits archive replacement, so checksum alone does not make a live archive URL immutable."
  ],
  "manualNotes": "Commit/hash: not created by this research child. Parent should capture bounded official bytes/headers if network access allows, write the repository report, validate Git state, and commit evidence/report only."
}
```
