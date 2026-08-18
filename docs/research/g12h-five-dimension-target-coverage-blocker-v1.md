# G12H Five-Dimension Target Coverage Blocker v1

## Decision

G12H remains `DRAFT / BLOCKED`. The PASSED rule-authority publication is exact,
but its five authority dimensions do not cover one common target interval. The
G12H analyzer contract therefore cannot truthfully freeze a success fixture, and
implementation remains unauthorized.

This finding does not modify any PASSED G08H or G12C/D bytes. It does not infer
current rules, extend finite bands, or grant provider, decision-grade, live, or
deployment authority.

## Immutable evidence

Source fixtures:

- declaration: `tests/fixtures/market_data/rule_authorities/cn-a-share-development-v1/declaration.json`;
- publication: `tests/fixtures/market_data/rule_authorities/cn-a-share-development-v1/publication.expected.json`;
- declaration hash: `sha256:6e0c60a75e957467a5cfe1b4e2bbbb786c463747ae96adf059c54ecef4a1b7b6`;
- manifest hash: `sha256:d85f6a85f7977a2096d1a26fe33a3892640bd27dc28e49b3e6b379650ab984c8`;
- immutable publication source: `832f53a74d3f74436ecae8672bd1c0dd3530c814`.

The declaration target is:

```text
UTC:        [2026-07-05T16:00:00Z, 2026-07-30T16:00:00Z)
local date: [2026-07-06, 2026-07-31) Asia/Shanghai
```

## Exact dimension coverage

| Dimension | Required applicability | Published coverage | Target result |
| --- | --- | --- | --- |
| Calendar | XSHE | `[2026-07-06, 2026-07-31)` local date | exact cover |
| Order rules | XSHE / Main board | `[2026-07-06, 2026-07-31)` local date | exact cover |
| Market fees | XSHE | `[2023-08-24T16:00:00Z, 2023-08-29T16:00:00Z)` across two contiguous bands | gap before target start |
| Stamp duty | XSHE | `[2023-08-24T16:00:00Z, 2023-08-29T16:00:00Z)` across two contiguous bands | gap before target start |
| Corporate-action entitlements | XSHE | `[2026-07-05T16:00:00Z, 2026-07-30T16:00:00Z)` | exact cover |

Using the frozen dimension order, the deterministic earliest result is:

```text
COVERAGE_GAP / market_fees
```

The complete five-dimension interval intersection is empty.

## Why the gap cannot be repaired locally

`docs/research/cn-a-share-commission-tax-primary-sources.md` explicitly freezes
G08E market-fee and stamp-duty authority only for the finite August 2023 fixture
interval. It forbids extrapolating an open-ended current rule even when later
public fee pages corroborate a rate. Extending those bands to July 2026 would
invent source closure and alter result-affecting authority.

Changing the G12H target to August 2023 would no longer bind the accepted G08H
profile timeline. Changing existing G08H or publication fixtures would violate
PASSED immutability. A synthetic success fixture would prove mechanics only and
cannot satisfy G12H's real immutable coverage prerequisite.

## Required additive prerequisite

Before G12H can become `READY`, freeze a new versioned authority set that provides:

1. one common finite target interval;
2. Calendar, order-rule, market-fee, stamp-duty, and corporate-action-entitlement
   exact coverage for the required Venue/applicability scopes;
3. source availability no later than the declared analysis time;
4. immutable source identities and correction/revision limits for every dimension;
5. a new profile/build declaration and G12C/D publication, without modifying the
   existing PASSED G08H or rule-publication artifacts.

Until then, no G12H analyzer production code, report/failure contract, RED success
fixture, or Gate status change is authorized.
