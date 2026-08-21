---
id: G12M-BHA-07
status: TERMINATED_H3
owner: Runtime integration single writer
produces:
  - exact resolved additive production Profile identity and registration
  - one-Bundle v3 funding consumption through the existing Runtime path
consumes:
  - G12M-BHA-04
  - G12M-BHA-05
  - G12M-BHA-06
depends_on:
  contract: [G12M-BHA-04, G12M-BHA-05, G12M-BHA-06]
  evidence: []
  write_conflict: [runtime-profile-registration, runtime-execution-orchestration, current-dirty-binance-profile]
fan_in: G12M-BHA-08
---

# BHA-07 Integrate Profile, Bundle, and adapter in Runtime

## Outcome

Compose the exact production Profile from BHA-04 authority inputs plus BHA-05/BHA-06
resolved execution inputs, register it in the existing resolver, and route the exact
execution-Bundle funding Event through BHA-06 into the existing G10E path.

## Start gate

Do not start until the owner has reconciled the current uncommitted changes in:

`packages/backtest-runtime/src/crypto_quant_backtest/binance_usdm_profile.py`

Record its pre-integration commit/fingerprint. Never overwrite, reset, or silently
resolve another owner's work.

## Inputs

- Accepted BHA-04 Profile-authority inputs and capability contract.
- Accepted BHA-05 execution Bundle fixture/identity.
- Accepted BHA-06 adapter and crosswalk contract.
- Existing Runtime resolution, hydration, timeline, financial dispatch, and Integrity
  seams.

## Interface and invariants

- Reconstruct and freeze the exact resolved Profile identity, then add a versioned
  production registration; do not flip the Development registration.
- Reuse the sole existing registry/resolver.
- Resolve the exact BHA-04 capabilities against the exact BHA-05 manifest.
- Hydrate/read one Bundle only; no Builder import, resampling, role fallback, or
  provider I/O.
- Emit the v3 Event at its market-data timeline instant, call BHA-06, and preserve the
  crosswalk into funding resolution/dispatch evidence.
- Grade remains owned by existing Profile/Integrity policy, not by G12M.

## Expected write set

The single writer may edit the minimum existing Runtime registration/orchestration
files discovered by call-site tracing, plus focused tests/fixtures. Candidate shared
seams include `binance_usdm_profile.py`, resolution registration, execution-input
hydration, timeline dispatch, and financial dispatch. Do not edit all candidates
unless the actual call graph requires it.

No Builder, generic MarketEvent, Kernel funding resolver, public Runtime root, or
accepted fixture changes.

## Failure precedence

1. unaccepted Profile/Bundle/adapter identity;
2. registration key/version conflict;
3. capability resolution failure;
4. cross-Bundle or stream mismatch;
5. timeline causality mismatch;
6. adapter/crosswalk failure;
7. funding dispatch rejection;
8. Integrity incompatibility.

## Acceptance

- Development registration remains byte/behavior compatible.
- Production resolution succeeds only for the exact BHA-04 authority-input and
  BHA-05 Bundle identities.
- Tampered capability, stream, timing, or crosswalk fails closed.
- End-to-end Runtime trace reaches existing G10E without Builder import.
- Focused, adjacent Runtime/Profile/G10E, and architecture suites pass.
- Ruff/LSP/diff/secret scan and independent integration review pass.

## Exclusions

- Persisted canonical Run/acceptance journey.
- G12M assessment.
- Governance/status updates.
