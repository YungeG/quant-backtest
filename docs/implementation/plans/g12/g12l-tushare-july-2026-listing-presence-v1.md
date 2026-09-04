---
id: G12L-TUSHARE-JULY-2026-LISTING-PRESENCE-V1
readiness: ACCEPTED_SOURCE_AND_POST_ASSESSMENT_BINDING
status: PASSED
owner: Tushare acquisition + market-bundle-builder observation + Runtime post-assessment binding
depends_on:
  contract: [ADR-0008, ADR-0010, G12I-TUSHARE-CN-A-SHARE-DAILY-SOURCE-BOUNDED-V2]
  evidence:
    - G12L-TUSHARE-CN-A-SHARE-LISTING-SOURCE-BOUNDED-V2
    - G12M-TUSHARE-LISTING-PRESENCE-BINDING-V1
---

# G12L Tushare July-2026 listing presence v1

## Outcome

Acquire and observe exact `bak_basic` rows for `000001.SZ` on the 19 accepted G12I
July-2026 provider dates, then bind that new report as a direct additive successor to
the accepted G12M post-assessment listing binding.

The accepted statement may be only: at the new acquisition time, Tushare through the
ADR-0010 approved transport returned one matching historical-list row for each of the
19 exact provider dates. This does not prove listing between dates, uninterrupted
listing, provider completeness, authoritative absence, survivorship safety, provider
availability before the Run, or causal execution input. Existing G12I, G12L, G12M
route/Run/assessment/binding-v1, grades, and fixtures remain immutable.

## Full implementation packet

**Status: READY**

### Authority

| ID | Source | Requirement or invariant |
| --- | --- | --- |
| A1 | user-approved continuation | Strengthen the exact execution-window listing evidence without changing grade/live/deployment. |
| A2 | ADR 0008 | Runtime binds exact possessed source bytes but does not mint grade, import Builder, or perform I/O. |
| A3 | ADR 0010 | Use only the fixed approved proxy endpoint, `x-api-key`, no redirects/failover/credential persistence, 0.5-second spacing, and bounded retry. |
| A4 | accepted G12I report | The only dates are `20260706..20260730` accepted observed trading dates below. |
| A5 | accepted G12L listing v2 | Fixed identity is `000001.SZ / xshe:000001 / 平安银行 / list_date=19910403`; strict lifecycle/completeness claims remain false. |
| A6 | accepted G12M binding v1 | New Runtime binding must directly supersede binding `sha256:ab9b0b750e55e34ff6e8fe5fb9e388143b83aa5140357061dfc7fe4c11ee6f8c` without altering its base assessment or grades. |
| P1 | bounded live readiness probe | All 19 exact calls returned one `平安银行` row in one attempt; this is readiness evidence only, not retained acceptance evidence. |

### Exact dates

```text
20260706 20260707 20260708 20260709 20260710
20260713 20260714 20260715 20260716 20260717
20260720 20260721 20260722 20260723 20260724
20260727 20260728 20260729 20260730
```

### Ownership and write sets

One writer owns the worktree `/tmp/backtest-g12l-july-listing-presence-v1`.

D1 acquisition and evidence:

```text
tools/acquisition/cn_a_share_tushare_july_listing_presence_v1.py
tests/tools/acquisition/test_cn_a_share_tushare_july_listing_presence_v1.py
tests/architecture/test_g12l_tushare_july_listing_presence_v1_boundary.py
tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/acquisition-receipt.json
tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/response/bak-basic/*.json
```

D2 pure Builder observer:

```text
packages/market-bundle-builder/src/crypto_quant_bundle_builder/tushare_cn_a_share_july_listing_presence_v1.py
tests/bundle_builder/providers/tushare/test_cn_a_share_july_listing_presence_v1.py
tests/architecture/test_g12l_tushare_july_listing_observer_v1_boundary.py
tests/fixtures/market_data/providers/tushare/g12l-july-listing-presence-v1/observation-report.expected.json
```

D3 Runtime successor binding:

```text
packages/backtest-runtime/src/crypto_quant_backtest/g12m_tushare_july_listing_presence_binding_v2.py
tests/runtime/g12m/test_tushare_july_listing_presence_binding_v2.py
tests/architecture/test_g12m_tushare_july_listing_presence_binding_v2_boundary.py
tests/fixtures/runtime/g12m-tushare-july-listing-presence-binding-v2/identity.expected.json
```

This plan is the only shared contract file before governance fan-in.

### Flow and seams

```text
D1: 19 fixed bak_basic calls -> exact bytes + receipt + 19-member G12A Snapshot
D2: receipt/Snapshot + accepted G12I bytes + accepted 2024 listing bytes + catalog
      -> exact July listing-presence report or structured failure
D3: accepted G12M binding-v1 object + exact D2 canonical bytes + bound_at
      -> direct-successor binding-v2 or structured failure
```

No existing acquisition tool, observer, route, assessment, facade, root export,
Profile, Bundle, Run, Integrity result, or accepted fixture is edited.

### D1 exact transport and evidence

Calls are exactly, in date order:

```text
bak_basic(
  trade_date=<exact date>,
  ts_code=000001.SZ,
  fields=trade_date,ts_code,name,list_date,
)
```

The new tool reuses the accepted sibling transport helpers for canonical POST,
no-redirect behavior, gzip, redacted errors, retries, and headers. Output is
no-clobber/receipt-last and contains exactly 19 response members under
`response/bak-basic/<date>.json` plus `acquisition-receipt.json`. Every response must
be one exact row; every qualification flag remains false. The credential appears
only in the request header and never in output, URL, body, exception, fixture, log,
or provenance.

### D2 observer symbols

```text
TushareCnAShareJulyListingPresenceReportV1
TushareCnAShareJulyListingPresenceOutcomeV1
observe_tushare_cn_a_share_july_listing_presence_v1(...)
```

Inputs are exact receipt bytes, `SourceSnapshot`, accepted G12I canonical bytes,
accepted 2024 listing-report canonical bytes, and exact singleton
`InstrumentCatalog`. The observer imports no Runtime and performs no I/O. It verifies:

- exact accepted G12I file/report identity and the 19-date tuple;
- exact accepted 2024 listing file/report identity, singleton catalog, name/list date;
- exact receipt/Snapshot/member hashes, endpoint, request order, row counts, and false flags;
- canonical provider response schemas and terminal pages;
- exactly one row per date with `(date, 000001.SZ, 平安银行, 19910403)`; and
- all source-row hashes plus canonical report replay.

The report binds observed-at time, direct upstream identities, all 19 dates/rows,
limitations, null predecessor, and false completeness/lifecycle/absence/grade/live/
deployment flags.

D2 failure precedence:

1. `INVALID_INPUT`;
2. `EVIDENCE_INVALID`;
3. `UPSTREAM_IDENTITY_MISMATCH`;
4. `REQUEST_SCOPE_MISMATCH`;
5. `RESPONSE_SCHEMA_MISMATCH`;
6. `RESPONSE_PAGE_INCOMPLETE`;
7. `SOURCE_OBSERVATION_CONFLICT`;
8. `REPORT_BINDING_MISMATCH`.

### D3 successor binding symbols

```text
G12MTushareJulyListingPresenceBindingV2
G12MTushareJulyListingPresenceBindingOutcomeV2
bind_g12m_tushare_july_listing_presence_v2(...)
```

The pure off-root Runtime binding consumes the exact accepted binding-v1 object and
possessed canonical D2 bytes. It records binding-v1 hash as the direct predecessor,
copies the unchanged base assessment/Run/requested-result grades, binds the 19-date
report identity, and requires `bound_at` not earlier than the D2 observation.

D3 failure precedence:

1. `INVALID_EXACT_INPUT_TYPE`;
2. `PREDECESSOR_BINDING_MISMATCH`;
3. `MALFORMED_OR_NONCANONICAL_JULY_REPORT`;
4. `JULY_REPORT_IDENTITY_MISMATCH`;
5. `BINDING_TIME_INVALID`;
6. `BINDING_RECONSTRUCTION_MISMATCH`.

The binding explicitly records that evidence is post-Run/post-assessment and not
causal input. It does not change the accepted base assessment or grade.

### Security, compatibility, and forbidden paths

- Untrusted bytes are deep-exact, duplicate-key safe, non-finite/float rejecting,
  canonical, and content-hash verified.
- No naked hash, generic mapping, provider registry, policy DSL, fallback endpoint,
  automatic date discovery, nearby-date substitution, or missing-row inference.
- No Runtime→Builder import and no Builder→Runtime import.
- Existing accepted files are protected by architecture SHA-256 sentinels.
- A corrected source requires a separately accepted new Snapshot/report/binding; no
  silent replacement or current-value lookup exists.

### Validation

- D1: focused fake transport, redirect/gzip/retry/no-clobber/credential tests and one
  formal live capture.
- D2: exact real fixture/golden, failure precedence, constructor bypass, upstream and
  catalog mutation, architecture isolation.
- D3: exact predecessor/report/time/grade/golden and constructor-bypass tests.
- Candidate: adjacent G12I/G12L/G12M tests, import boundary, LSP/lens, compile/lock/
  diff, gitleaks, and independent blocker review.
- Acceptance: one full-repository run, governance review, protected dirty hashes,
  fast-forward main, and no push without fresh approval.

### Open decision

None.

## Acceptance closure

```text
contract: 4ca69b6ccb2d766ec9e304d3f7624f587685c771
acquisition tool: da91f414911263e483c0b4a34774d5d243e069d9
evidence: a5c67421083c406c7a2ad2207429128ea6fe44a3
observer: 9aa99d9b338a938bf69e0d39983dcc9137741127
Runtime binding: f6c81149b5a97088576e0f6d0fb5ed294b2cec05
receipt file: sha256:b2160a51acc6a642fe471c87b946237bdb37b1087f56fc2e6262d86a834fb581
Snapshot: sha256:3b8b35744bd14974e71ca7de4fe00d229290061df38b29cedf0f5d2eb3ca378c
request scope: sha256:388fa357808ab359366b9ac1dad808ea53b01be07d1b83a80d798a1b75268cce
G12L report: sha256:4c829bf707bf0876ada550ad44682d0fc362025379afe233b98e9d7751e22052
G12M binding: sha256:30d1ef7480ad435e5a1e3f4948891c7d2f8c412b16731155bd5d2bf14126342f
```

All 19 formal calls returned exactly one accepted row in one attempt. Adjacent
validation passed 29 tests during D2 review, the full repository passed 2424 tests,
the 138-file import boundary passed, LSP/lens and gitleaks were clean, and independent
D1/D2/D3 reviews returned `PASS` after blocker repair.

Acceptance remains post-hoc and source-bounded. It does not establish provider-time
availability before the Run, listing between observed dates, uninterrupted lifecycle,
provider completeness/finality, authoritative absence, survivorship safety, grade
upgrade, live eligibility, or deployment authorization.
