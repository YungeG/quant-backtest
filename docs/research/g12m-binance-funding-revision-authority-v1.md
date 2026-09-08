---
id: G12M-BINANCE-FUNDING-REVISION-AUTHORITY-V1
status: BLOCKED
owner: G12M-BHA-01B
scope: Binance USDⓈ-M GET /fapi/v1/fundingRate correction and revision authority for settled 2024 rows
conclusion: UNKNOWN_CAUSAL_BLOCKER
---

# Binance USDⓈ-M funding revision authority v1

## Decision

**UNKNOWN — causal blocker.** Exact unauthenticated first-party bytes now establish
bounded endpoint request/response shape and post-target schema evolution, but none
identifies the exact revision of a settled row that was visible at settlement. A
later current-state row therefore cannot prove equality with the 2024
settlement-visible revision.

Missing permanent finality alone could remain an ADR 0008 limitation. Missing
settlement-visible revision identity is independently causal and cannot be
downgraded.

## Accepted evidence method

The acceptance basis is the five-member canonical G12A `SourceSnapshot` at
`evidence/g12m-binance-funding-revision-authority-v1/source-snapshot.json`:

1. official Binance Python Futures connector bytes pinned at a 2022 commit;
2. official Binance modular connector response-model bytes pinned at 2025 and 2026
   commits;
3. the official modular connector changelog pinned at the 2026 response change;
4. one exact unauthenticated Binance Futures testnet response.

Every member has exact request scope, nanosecond receipt time, HTTP status and raw
headers, body byte count, SHA-256, and a local receipt. GitHub bytes replay against
both raw HTTP and `git show <commit>:<path>`. Search-provider excerpts remain
secondary acquisition aids: they are not SourceSnapshot members and are not the
acceptance basis.

Production `developers.binance.com` and `fapi.binance.com` remained unreachable:
both resolved into `198.18.0.0/15` and failed TLS before any HTTP response. The
exact failures are retained. No authentication, cookie, credential, or API key was
used.

## Findings

### 1. A target-preceding official connector exposes business-time selectors, not row vintage

At official commit `d30576a6d8e6edb706c8b013eb11167b58e9c33a`, dated
2022-08-29, `binance/um_futures/market.py` defines Funding Rate History as:

> `GET /fapi/v1/fundingRate`
>
> `symbol`, `limit`, `startTime`, `endTime`
>
> `return self.query("/fapi/v1/fundingRate", params)`

Accepted raw member: `github/funding-rate-request-2022.py`, lines 242-263.

This establishes that the endpoint and those request parameters predate the target
2024 rows. It exposes no `asOf`, revision, publication-time, or snapshot-vintage
selector in that accepted interface. This is not a claim about undisclosed Binance
systems or every later parameter.

### 2. Accepted first-party response shapes name business fields, not row revisions

The official generated response model pinned at commit
`38996023660752a75acf7ebbc4f9a504e10e336f` names:

> `symbol`, `fundingRate`, `fundingTime`, `markPrice`

The model pinned at commit `e44cdc9e57c76154f08676764bb6f21fbdb49c4a`
names the same fields plus `rateType`. The separately fetched exact testnet body
contains two rows with `symbol`, `fundingTime`, `fundingRate`, and `markPrice`.

None of those exact surfaces names a revision ID, predecessor, corrected-at time,
provider publication time, or immutable row checksum. The generated model allows
additional properties, so the accepted statement is bounded to named fields on
these exact surfaces; it is not a provider-global absence claim.

### 3. Current schema is demonstrably not wholly target-effective

The 2025 pinned response model has four named fields. The 2026 pinned model adds
`rateType`, and the pinned official changelog states:

> `## 15.0.0 - 2026-07-28`
>
> `Modified response for get_funding_rate_history() (GET /fapi/v1/fundingRate)`
>
> `property rateType added`

Accepted raw member: `github/usds-futures-changelog-2026.md`, lines 3 and 28-30.

That exact dated evolution prevents backdating the whole current schema to 2024.
It proves schema evolution only; it neither confirms nor excludes corrections to
settled funding values.

### 4. Current-state retrieval cannot recover settlement-visible revision identity

The accepted target-preceding request interface selects business-time range/count,
while the accepted response surfaces expose current business fields without named
revision lineage. Consequently, a later response can establish only the bytes
received later. Without a retained settlement-time response or first-party lineage,
it cannot distinguish an unchanged original value from a later-corrected value.

This is a capability limitation. It is **not** a positive claim that Binance revises
settled rows.

### 5. No permanent-finality guarantee is established by the accepted raw set

No accepted member states that settled rows are immutable forever or binds them to
an immutable provider checksum. This supports only: **the enumerated accepted
first-party surfaces do not provide the required guarantee**. It does not establish
that no such statement exists elsewhere.

### 6. Search excerpts are secondary only

The endpoint documentation, developer change-log extraction, and funding FAQ search
passages remain useful for locating terminology and bounding further acquisition.
They do not carry raw HTTP-header fidelity and are excluded from the canonical
SourceSnapshot. In particular, the search-extracted 2023-11-01 `markPrice` passage
is not used as independent acceptance authority; no claim here depends on it.

## Answers to BHA-01B questions

| Question | Answer | Consequence |
| --- | --- | --- |
| Does Binance document corrections or revisions to settled funding rows? | Not in the exact accepted first-party byte set. | Bounded negative only; no provider-global claim. |
| Does Funding Rate History expose revision identity or only current state? | Accepted interfaces expose business-time request parameters and named business response fields, with no named row-vintage selector or revision lineage. | **Causal blocker.** |
| Can the current endpoint return a value revised after original settlement? | Undetermined. The accepted interface cannot distinguish that case from an unchanged original value. | **Causal blocker.** |
| Is a permanent finality/checksum guarantee available? | Not established by the accepted raw set. | Explicit ADR 0008 limitation; cannot cure the identity blocker. |
| What is allowed under the governing G12M plan? | Preserve source bounds and fail closed; do not backdate current bytes or mint ResultGrade. | `UNKNOWN_CAUSAL_BLOCKER`. |

## Closed limitation set returned to BHA-02

The canonical set is retained at
`evidence/g12m-binance-funding-revision-authority-v1/closed-limitations.md`.

- **BHA01B-B1 — BLOCKER:** no exact accepted identity for the row revision visible
  at settlement.
- **BHA01B-B2 — BLOCKER:** later current-state bytes cannot distinguish original
  versus later-corrected value.
- **BHA01B-L1 — LIMITATION:** no accepted permanent-finality or immutable checksum
  guarantee.
- **BHA01B-L2 — LIMITATION:** negative findings are limited to enumerated exact
  first-party surfaces.
- **BHA01B-L3 — LIMITATION:** no accepted production response or revision-policy
  bytes from the 2024 settlement period; current schema includes a dated 2026 field.
- **BHA01B-L4 — LIMITATION:** production docs/API remained inaccessible through the
  runtime fake-IP path; accepted raw bytes come from pinned official GitHub and
  public testnet surfaces.
- **BHA01B-L5 — LIMITATION:** source-bounded research cannot mint/upgrade ResultGrade
  or silently alter prior Runs.

## Evidence identities and review

- SourceSnapshot: `sha256:e8faeb5a146c0ff85f5afca6f740ee9a925a3d47134c4d3495b26fdb5e4b8f25`.
- Content tree: `sha256:935355b119ac9445a17fc7e3be19eeb8156914081df21519604182a9fed73f5a`.
- Primary-source review: `evidence/g12m-binance-funding-revision-authority-v1/primary-source-review.md`.
- Full source URLs, receipts, headers, hashes, Git blob OIDs, fake-IP failures, and
  replay boundary: `evidence/g12m-binance-funding-revision-authority-v1/README.md`.
