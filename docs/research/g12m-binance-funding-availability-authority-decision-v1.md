---
id: G12M-BINANCE-FUNDING-AVAILABILITY-AUTHORITY-DECISION-V1
owner: G12M-BHA-02
status: DECIDED
outcome: H3
label: NO_CAUSAL_AUTHORITY
---

# G12M Binance funding availability authority decision v1

## Decision

**`H3 — NO_CAUSAL_AUTHORITY`.** H1 and H2 are unavailable. The retained 2024
BTCUSDT rows remain permanently post-hoc-only, and no prospective authority plan is
authorized.

The exact H3 basis is:

1. Under ADR 0009, Provider Availability Time is the earliest defensible instant the
   exact event revision was usable. A prospective REST response receipt can bound
   local acquisition and participant usability no later than receipt, but it cannot
   prove that the earliest Provider Availability Time exactly equals `fundingTime`.
   Assigning `fundingTime` would therefore backdate availability rather than retain
   target-effective provider authority.
2. `MarketEvent` requires causal `available_time >= event_time`, while G10E fixes the
   funding publication/settlement Event at the exact `fundingTime`. A response first
   received after that instant cannot satisfy equality; a response observed before or
   at it still does not prove exact first availability at that instant.
3. Funding Rate History exposes current row state without a revision/as-of selector,
   predecessor identity, or complete correction history. Polling can retain sampled
   changes, but it cannot prove that no settlement-visible revision appeared and
   disappeared between samples, so it cannot prove the complete revision lineage
   required by G10E/G12.

The rejected prospective approach remains only this limitation statement; it is not
an authorized plan or implementation route.

## Branch termination and next route

`G12M-BHA-03` through `G12M-BHA-09` are `TERMINATED_H3`. BHA-02 emits no
availability authority, authority module, placeholder authority, source v3, Profile
input, Bundle, adapter, Run, assessment, grade, or executable code. `G12M-BHA-10` is
the only Ready route and owns final governance fan-in.

Accepted v1/v2 artifacts and packages remain unchanged. BHA-02 does not update the
Acceptance Matrix or G12 README.

## Bound evidence

The canonical decision at
[`decision.json`](../../evidence/g12m-binance-funding-availability-authority-decision-v1/decision.json)
binds the final accepted Wave 0 tips and exact evidence hashes:

- governance `d9ec8631385247249fcd91bd814c1342948c53b5`;
- BHA-01A `7a808d3b7b7a58a354212e0da0fc67c3dcefd85c`;
- BHA-01B `366575914cd4066ad6cfa593b8df219df7021c54`;
- ADR 0009 `sha256:cba2054010ed8acc9aeb57fb3ce57628163134e1d1382ab88e8384f03f68a94f`;
- BHA-01A report `sha256:76a47f7c95ea958e519edceb0d4789c82bc857641532e84dca147e30f1a536d5`;
- BHA-01B report `sha256:8374d76c09df8d8479bc9364d949aafa47b138f63fa9eac9a4e6d8fad0885fc4`;
- accepted 2024 v2 report identity
  `sha256:29e639615c1e5f5fa05ffdff9bc77a630d56838c7b0e70230177922bdbffc37b`.

No credential, cookie, authorization header, environment value, raw exception, or
account identifier is retained in this decision lane.
