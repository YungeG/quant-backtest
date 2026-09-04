# G12M Binance funding settlement availability authority v1

## Closed contribution

**`PROSPECTIVE_ONLY`.** First-party Binance material retained by this lane does not prove, for the three BTCUSDT rows on 2024-01-01, that the exact Funding Rate History `fundingRate` and `markPrice` revision was usable at the settlement instant. The 2024 source remains post-hoc-only. A separate future capture may establish contemporaneous participant availability for future settlements; it must not backdate these rows.

This is the G12M-BHA-01A settlement/availability contribution only. It does not decide correction or revision closure.

## Exact target and retained evidence

Target request:

```text
GET https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&startTime=1704067200000&endTime=1704153599999&limit=100
```

Target funding slots:

```text
2024-01-01T00:00:00Z
2024-01-01T08:00:00Z
2024-01-01T16:00:00Z
```

The dedicated subtree is [`evidence/g12m-binance-funding-settlement-availability-v1/`](../../evidence/g12m-binance-funding-settlement-availability-v1/). It retains exact official body bytes where fetchable, request receipts, a deterministic G12A SourceSnapshot, hashes, this lane's structured assessment, and negative-search/access limitations.

| Artifact | SHA-256 | Effective-date basis |
| --- | --- | --- |
| [Target Funding Rate History response](../../evidence/g12m-binance-funding-settlement-availability-v1/raw/target-funding-history-response.json) | `e9f73f9c845c28abb31037d8230df2d6f13d5d368c43436e891fcc757372c338` | Exact accepted first-party row bytes, acquired in 2026; proves row content, not 2024 availability. |
| [Official Binance connector `market.py` pinned to `d30576a6`](../../evidence/g12m-binance-funding-settlement-availability-v1/raw/binance-futures-connector-python-market-d30576a.py) | `e50bd98895e218893124db4cce7126dd128d3621d7d0d14f3545ee9bbf8e3533` | Immutable official commit state before 2024. |
| [Official commit patch](../../evidence/g12m-binance-funding-settlement-availability-v1/raw/binance-futures-connector-python-d30576a.patch) | `49e23a8aefc09dcfa08a7efd788b9076451d0527fa1eac44284656f7860dc689` | Official patch dates commit `d30576a6d8e6edb706c8b013eb11167b58e9c33a` to 2022-08-29. |
| [Current Binance Support article response](../../evidence/g12m-binance-funding-settlement-availability-v1/raw/binance-support-article-360033525031.json) | `94104929c6a1c381a5435bc235d9ac12f26645ad649583b05e1c1de8464ccc30` | Mutable article published 2019-09-09 and last updated 2026-03-06; current-only because no first-party historical body/version was retained. |

SourceSnapshot:

```text
snapshot_id: sha256:ad5ee7b6981ffbd1048f3bd7b7966369e6cadc6654cde81aa670426f19d7c09f
content_tree_hash: sha256:218d95c3cb2ea769b2a52bc8633d162b76624e8dabb9829eccc5a60b2dcf0b1d
provenance_hash: sha256:d93b2459b858da590ac15093251909b3dc561c0aa2ccefa05e03ae19c3db8e54
```

See [manifest](../../evidence/g12m-binance-funding-settlement-availability-v1/manifest.json), [hash ledger](../../evidence/g12m-binance-funding-settlement-availability-v1/sha256sums.txt), and [structured assessment](../../evidence/g12m-binance-funding-settlement-availability-v1/research-assessment.json).

## Answers

### 1. What does `fundingTime` mean?

**Documented fact:** the official connector pinned before 2024 identifies `GET /fapi/v1/fundingRate` as Funding Rate History, accepts `startTime`/`endTime`, and returns data in ascending order. The exact target response has `fundingTime` values at 00:00, 08:00, and 16:00 UTC.

**Inference:** `fundingTime` identifies the scheduled funding event/settlement slot represented by the history row. It is not a publication timestamp.

**Limitation:** no retained target-effective first-party passage defines `fundingTime` more precisely or equates it with the first instant the exact row was exposed to participants.

### 2. When is the final rate fixed and applied?

The current Binance Support article says:

> “The funding rate is then calculated with this 8-Hour interest rate component and the 8-Hour premium component. A +/- 0.05% damper is also added. For example, the funding rates calculated from 00:00 - 08:00 are exchanged at 08:00.”

It also uses a later example in which the rate “at the funding rate settlement time” controls the outcome. This supports **current application/exchange at the scheduled funding time**.

It does not close the target question. The retained article was updated in 2026, so its exact wording is not proven effective on 2024-01-01. It also does not state when the final REST history revision becomes readable. Current Binance wording separately warns:

> “There is a 15-second deviation in the actual funding fee transaction time.”

Application, account transaction, and REST publication therefore cannot be collapsed into one timestamp without further authority.

### 3. Is Funding Rate History `markPrice` the exact settlement mark?

The current support article states:

> “Funding Amount = Nominal Value of Positions * Funding Rate”
>
> “(Nominal Value of Positions = Mark Price * Size of a Contract)”

The exact target rows contain `markPrice`. These facts make an association plausible, but they do not prove that the history field is byte-for-byte the exact mark used for each settled charge. No retained target-effective first-party passage makes that equality, and no nearby mark-price stream or kline is substituted.

Result: **not proven**.

### 4. Was the exact rate + mark revision usable at settlement?

**No historical proof was found.** The row bytes have no provider publication timestamp, first-appearance timestamp, or historical availability field. The accepted acquisition occurred in 2026. Binance's current explanation of settlement does not say that the exact Funding Rate History row was exposed at or before `fundingTime`.

Therefore this lane cannot establish:

```text
provider_available_time == funding_time
```

for either the rate or mark, and `HISTORICAL_EQUALITY_SUPPORTED` is rejected.

## Effective-date boundary

Only the pinned official connector source is immutably pre-target. It proves endpoint existence and request/order behavior, not settlement or availability semantics. The target response proves exact returned values but was observed later. The support article is current mutable content with a 2026 update time. Combining these sources cannot manufacture target-effective 2024 publication semantics.

## Negative search and access record

The bounded first-party search found no Binance historical publication timestamp, first-appearance log, or target-row availability field.

Direct retrieval limitations were material:

- the current developer-doc URL redirected and then returned an HTTP 202 WAF challenge with zero body bytes;
- the legacy developer-doc URL and a new target `fapi` fetch failed through the configured network path;
- the configured fetch path reported reserved `198.18.0.0/15` remote addresses;
- exact bytes are retained only where the official-host request returned a body; direct-origin routing is not asserted;
- no raw bytes, headers, credentials, cookies, or provider availability were fabricated for blocked attempts.

The complete bounded attempt list is in the [structured assessment](../../evidence/g12m-binance-funding-settlement-availability-v1/research-assessment.json), with fetch-specific metadata in the [access-limitation receipt](../../evidence/g12m-binance-funding-settlement-availability-v1/receipts/access-limitations.json). Secondary sources were not used as authority.

## Prospective boundary

A future, separately versioned source case can capture exact first-party history rows and contemporaneous account/settlement evidence around the funding instant, with local receipt timestamps and repeated checks for later changes. Such evidence may establish participant usability for those future rows. It cannot retroactively establish the 2024 rows and does not authorize G12M D2-D8 for the existing case.

## Decision contribution

```text
PROSPECTIVE_ONLY
```
