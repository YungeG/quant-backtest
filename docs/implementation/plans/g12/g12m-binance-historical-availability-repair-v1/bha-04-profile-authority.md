---
id: G12M-BHA-04
status: DRAFT_WAITING_H1
owner: Runtime Profile authority writer
produces:
  - additive Binance Profile authority inputs and limitation dispositions
  - exact required execution-Bundle capabilities
consumes:
  - G12M-BHA-02 H1 authority
  - existing Binance Profile component authorities
depends_on:
  contract: [G12M-BHA-02, existing Runtime Resolution contracts]
  evidence: [accepted fee, rounding, settlement, price-purpose, account authorities]
  write_conflict: []
fan_in: [G12M-BHA-05, G12M-BHA-06, G12M-BHA-07]
---

# BHA-04 Freeze Profile authority inputs and capability contract

## Outcome

Freeze additive provider-specific Profile authority inputs, limitation dispositions,
and exact capability requirements without claiming the final resolved Profile
identity or registering it in the shared Runtime seam.

## Inputs

- Accepted BHA-02 H1 authority identity, funding-source limitation disposition, and
  exact v3 funding capability/version/payload contract.
- Existing Binance Market/Simulation Profile and component contracts.
- Accepted account/financial-event, bar, price-purpose, fee, rounding, settlement,
  Build, Profile, and Environment authorities.

## Interface and invariants

Reuse existing Profile/component/resolution types. Add only the smallest closed
provider-specific authority value needed to bind:

- exact component identities and digests;
- production scope and target interval;
- exact capability keys/versions required from one execution Bundle;
- explicit disposition of every decision-grade blocking limitation;
- compatible Build/Profile/Environment identities.

This node does not resolve the exact funding record, finalize a production Profile
identity, register a Profile, mint a Result, grade a Run, or create a second
registry/resolver. If any authority input remains decision-grade blocking, emit a
canonical rejection and stop BHA-05 onward. BHA-07 combines these accepted inputs with
BHA-05 and BHA-06 to produce the exact resolved Profile identity.

## Expected write set

- One additive off-root Runtime Profile-authority module or value.
- Focused tests and golden fixtures for accepted/rejected authority.
- No edit to `binance_usdm_profile.py`, `resolution.py`, Runtime roots, or shared
  registration tables; BHA-07 owns those writes.

## Failure precedence

1. malformed component authority;
2. component identity/scope mismatch;
3. unresolved decision-grade limitation;
4. capability/version conflict;
5. Build/Profile/Environment incompatibility;
6. canonical reconstruction mismatch.

## Acceptance

- Every blocking limitation has an exact accepted or rejected disposition.
- Golden Profile-authority-input/capability bytes and hashes.
- Development inputs cannot reconstruct as production-authority inputs.
- Missing/forged component or capability fails closed.
- Focused Runtime/Profile and architecture tests, Ruff/LSP/diff/secret scan.
- Independent grade-authority review.

## Exclusions

- Exact resolved Profile identity, shared registration, or resolver edits.
- Execution Bundle construction.
- Event adapter, canonical Run, Integrity report, or G12M assessment.
