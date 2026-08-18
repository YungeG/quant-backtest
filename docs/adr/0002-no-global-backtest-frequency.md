# ADR 0002: No Global Backtest Frequency

- Status: Accepted
- Date: 2026-08-18
- Scope: MRMD-01

A Backtest Run does not have one global market-data frequency. Strategy signal observations, decision cadence, execution-simulation data, and valuation data are separate authorities and may use different immutable streams. Strategies continue to declare signal lookbacks through `DecisionSchedule` and `LookbackRequirement`; Profile/preparation owns execution and valuation bindings; preparation freezes one run-scoped binding set whose signal, execution, and valuation identities enter the existing decision, execution, and snapshot semantic hashes and therefore the Semantic Run ID.

Runtime never resamples. Builder may materialize each requested Bar stream before the run through an accepted aggregation contract. MRMD-01 v1 accepts only existing G12G direct point-to-Bar lineage; nominal durations and strings such as `1m` or `5s` do not prove a resolution relationship because Session breaks and irregular buckets make bucket geometry authoritative. Missing finer evidence and coarse-to-fine requests fail closed; no interpolation, forward fill, synthetic bars, implicit stream fallback, or mutation of PASSED v1 bytes is allowed.
