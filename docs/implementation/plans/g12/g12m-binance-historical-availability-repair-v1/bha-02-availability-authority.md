---
id: G12M-BHA-02
status: DRAFT_WAITING
owner: Builder authority single writer
produces:
  - one H1/H2/H3 authority decision
  - H1-only canonical row availability authority
consumes:
  - G12M-BHA-00
  - G12M-BHA-01A
  - G12M-BHA-01B
depends_on:
  contract: [G12M-BHA-00]
  evidence: [G12M-BHA-01A, G12M-BHA-01B]
  write_conflict: []
fan_in: [G12M-BHA-03, G12M-BHA-04, G12M-BHA-10]
---

# BHA-02 Decide and freeze provider availability authority

## Outcome

Own the sole H1/H2/H3 decision. On H1, publish one closed provider-specific canonical
authority for the three retained rows. On H2/H3, publish only the blocker decision and
terminate BHA-03 through BHA-09.

## Inputs

- Accepted BHA-00 governance commit.
- Accepted BHA-01A settlement research bytes/report.
- Accepted BHA-01B revision research bytes/report.
- Exact accepted v2 observation report identity.

## Minimal H1 contract

Freeze exact rows shaped as:

```text
(funding_time, provider_available_time, authority_source_hash)
```

with `provider_available_time == funding_time` for every row. Bind provider, dataset,
instrument, source document/Snapshot hashes, effective interval, authority basis,
acquisition time, limitations, predecessor, and canonical authority hash.

Also freeze the exact provider-specific v3 funding capability key/version, Event
payload fields, decimal scales, purpose, and timeline phase. BHA-03 and BHA-04 must
consume this shared contract unchanged so parallel source/Profile work cannot drift.

Use one provider-specific value/module. Do not add an interface, policy object,
configurable delay, registry, or generic resolver.

## Branch rules

1. H1 — both exact settlement-time availability and exact settlement-visible revision
   are supported; emit the canonical authority.
2. H2 — historical equality is unsupported but prospective capture is feasible; emit
   a post-hoc-only decision and require a separate prospective plan.
3. H3 — causal authority remains unknown; emit the permanent blocker decision.

H2/H3 must not emit a placeholder authority.

## Expected write set

- One off-root Builder module for the decision/authority value.
- Focused Builder tests and H1/H2/H3 golden fixtures.
- One provider-specific authority-decision artifact.

No Builder root export, accepted v2 file, Runtime, Kernel, shared registry, or research
evidence mutation.

## Failure precedence

1. malformed canonical bytes;
2. invalid or non-first-party source identity;
3. target-effective scope mismatch;
4. row/provider/instrument mismatch;
5. settlement-time inequality;
6. revision-vintage blocker;
7. invalid direct predecessor;
8. unsafe serialized field.

## Acceptance

- Focused canonical reconstruction, constructor-bypass, scope/time, and branch tests.
- Golden authority/decision bytes and SHA-256.
- Builder boundary and secret-safety tests.
- Independent authority and data-contract review.

## Exclusions

- Source v3 publication.
- Prospective capture implementation.
- Profile, Bundle, Runtime, Run, or G12M assessment.
