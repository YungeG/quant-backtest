# G11 Portfolio Strategy Runtime Execution DAG

## Outcome

Replace only the precomputed Target entry with a deterministic, auditable Portfolio Strategy Runtime. G11 must reuse the existing Validator, Allocation, Risk, Planning, Execution, Accounting, Runner, and Evidence paths rather than create parallel downstream economics.

The Gate status registry remains `docs/implementation/acceptance-matrix.md`. Files in this directory own active G11 plan prose and dependencies, not status.

## Shared invariants

- Strategy receives least-authority immutable views, never MarketBundle, account financial state, filesystem, network, process, or wall clock handles.
- All behavior-affecting Strategy state, model selection, random position, observation evidence, and schedule identity is canonical and replayable.
- Observation visibility is point-in-time and revision-aware before Strategy invocation.
- Strategy output enters the existing G04 validation and atomic DecisionBatch seam.
- G11 does not own a second Order, Fill, Fee, Journal, Ledger, Margin, or Result path.
- All outputs remain development-only until G12 data qualification; deployment authorization remains false.

## Execution DAG

```text
G11A(PASSED) ─→ G11B ─┬─→ G11C ───────────────┐
                      ├─→ G11D ─→ G11E ──────┤
                      └────────────→ G11H ────┤
G02(PASSED) ─→ G11F ──┬─→ G11G ──────────────┤
                      └────────────→ G11H ────┤
G11A–G11H + G04(PASSED) ───────────→ G11I ─→ G11J
```

## Nodes

| Gate | Produces | Contract dependencies | Evidence dependencies | Expected implementation seam |
| --- | --- | --- | --- | --- |
| [G11B](g11b.md) | point-in-time revision-aware Observation View | G11A | frozen causality fixture | `observations.py` |
| [G11C](g11c.md) | point-in-time Universe query | G11A, G11B | listing/membership fixture | `universe.py` |
| [G11D](g11d.md) | named Bar/window access | G11A, G11B, BarDefinition | window/gap fixture | `observation_windows.py` |
| [G11E](g11e.md) | DecisionSchedule and Warmup | G11B, G11D | schedule/warmup fixture | `decision_schedule.py` |
| [G11F](g11f.md) | canonical StrategyState/checkpoint | G02 | restore fixture | `strategy_state.py` |
| [G11G](g11g.md) | named deterministic random streams | G11F | stream-isolation fixture | `random_streams.py` |
| [G11H](g11h.md) | ModelArtifact revision timeline | G11B, G11F | walk-forward fixture | `model_revisions.py` |
| [G11I](g11i.md) | Strategy invocation and atomic DecisionBatch | G11A–G11H, G04 | invocation fixture | `strategy_runtime.py` |
| [G11J](g11j.md) | precomputed-vs-Strategy parity | G11I, G07 | dual-entry fixture | parity tooling |

Expected seams are planning ownership, not frozen module names until the Gate reaches READY.

## Write-conflict policy

- G11B alone may deepen the existing `observations.py` public contract under its frozen acceptance.
- G11C–G11I should prefer disjoint deep modules; sharing one implementation file requires an explicit write-conflict edge.
- Root exports, the Acceptance Matrix registry, aggregate architecture text, final integration, and push remain serialized single-writer edits.
- Research, fixture design, and read-only review may fan out before implementation when consumed contracts are frozen.

## Ready queue

| Priority | Work | State | Unblocks | Write ownership |
| --- | --- | --- | --- | --- |
| 1 | G11B implementation | READY | G11C, G11D, G11H | observations core |
| 2 | G11F research/readiness | RESEARCH-READY | G11G, G11H | strategy state |
| 3 | G11C/G11D interface research | RESEARCH-READY | G11I / G11E | read-only until G11B passes |
| 4 | G11G/G11H | BLOCKED | G11I | wait for G11F / G11B |
| 5 | G11E | BLOCKED | G11I | wait for G11D |
| 6 | G11I | BLOCKED | G11J | fan-in G11A–H |
| 7 | G11J | BLOCKED | G11 release | wait for G11I |

## WIP and validation

- One active implementation writer.
- At most two research/readiness branches.
- Focused RED/GREEN tests during edits.
- Frozen Gate acceptance plus one full suite at implementation completion.
- PASSED recording performs document, hash, and repository checks without repeating unchanged expensive suites.
- G11I is the integration fan-in; G11J is the downstream economic parity fan-in.
