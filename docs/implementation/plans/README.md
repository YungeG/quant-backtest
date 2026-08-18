# Plan Decomposition and Execution DAG

## Purpose

Use this policy when an implementation plan becomes difficult to navigate, repeats status or acceptance facts, or hides independent work inside one linear document.

The goal is not more documents. The goal is a small roadmap index plus independently executable vertical plans connected by explicit dependencies.

## Active cross-Gate plans

- [MRMD-01 Multi-resolution Market Data](mrmd-01-multi-resolution-market-data.md) — `READY`; additive test-first implementation authorized.
- [PERF-OBS-01 Performance Observability](perf-obs-01-performance-observability.md) — `READY`; Runtime MRMD/PREP-only bounded non-authoritative observations.
- [PREP-COVERAGE-01 Runtime Multi-resolution Preparation/Preflight](prep-coverage-01.md) — `READY`; MRMD/PERF F2 test-first fan-in authorized.

## Separate artifact roles

Do not make one document serve every role:

| Artifact | Owns | Does not own |
| --- | --- | --- |
| Roadmap index | goals, release slices, links, dependency overview | detailed acceptance or execution logs |
| Gate plan | future interface, invariants, exclusions, dependencies, acceptance | historical command output |
| Research note | evidence and unresolved source facts | Gate status |
| Acceptance record | executed commands, immutable commit, artifact hashes | future design |
| Status registry | current Gate status and dependency keys | prose specification |

Each fact has one source of truth. Other documents link to it instead of copying it.

## Directory shape

New or actively revised large plans should move toward:

```text
docs/implementation/plans/
├── README.md
├── shared/
│   ├── invariants.md
│   └── validation.md
├── g08/
│   ├── README.md
│   ├── g08g.md
│   └── g08h.md
├── g11/
│   ├── README.md
│   ├── g11b.md
│   └── ...
└── g12/
    ├── README.md
    ├── g12a.md
    └── ...
```

A group `README.md` owns its local DAG and release outcome. A Gate file owns one independently testable vertical result, not one class or one source file.

## Gate header

Every Gate plan begins with a compact machine-readable header:

```yaml
id: G11B
status: DRAFT
owner: backtest-runtime
produces:
  - PointInTimeObservationView
consumes:
  - G11A.ObservationQuery
depends_on:
  contract: [G11A]
  evidence: []
  write_conflict: []
```

Status is written in one registry only. A Gate file may identify itself, but must not maintain a second independently editable status value once a registry exists.

## Dependency types

Record why work is blocked:

1. **Contract dependency** — an upstream interface or invariant must be frozen first.
2. **Evidence dependency** — research, fixture, provider data, or acceptance evidence is missing.
3. **Write-conflict dependency** — the work is logically independent but modifies the same public contract or files under the single-writer rule.

Dependencies should name consumed and produced artifacts where practical. Gate IDs alone often hide the real coupling.

## Decomposition test

Split a plan when at least one is true:

- it contains independent branches with different prerequisites;
- unrelated readers must load most of the document to find one task;
- status, acceptance, and research history are repeatedly duplicated;
- multiple teams or agents could work without sharing a public seam;
- the plan creates a recurring merge-conflict hotspot;
- one context window cannot hold the relevant plan without unrelated history.

Do not split by class, test file, or arbitrary line count. A node must still produce a useful, independently accepted vertical capability.

## Build the DAG

For each candidate node:

1. State the caller-visible result.
2. List consumed frozen contracts and evidence.
3. List produced contracts and artifacts.
4. List files or public seams it expects to modify.
5. Add contract, evidence, and write-conflict edges.
6. Reject cycles or replace them with a smaller shared predecessor contract.
7. Identify fan-out nodes and the later fan-in integration Gate.

A node is Ready only when all contract and evidence predecessors are complete. A Ready node may still wait for a write-conflict predecessor under the single-writer rule.

## Controlled parallelism

Use fan-out/fan-in:

```text
freeze shared contract
        ↓
independent Gate plans fan out
        ↓
integration/parity Gate fans in
```

Parallelize:

- research and evidence gathering;
- interface alternatives before freeze;
- fixtures for independent contracts;
- implementation in disjoint modules;
- read-only review and validation.

Serialize:

- edits to the same public contract;
- edits to the same source or status registry under single-writer policy;
- final integration, acceptance recording, and push.

Keep implementation WIP small: one active writer implementation and at most one or two research/readiness tasks. A large Ready queue is not a reason to create context switching.

## Design seams for parallel work

A DAG cannot create code-level independence when every Gate edits one module. Place interfaces so independent responsibilities can live in disjoint deep modules. Split by stable responsibility, not merely to increase file count.

Before fan-out, freeze the smallest shared interface. After fan-out, use one explicit integration Gate instead of making every child know every sibling.

## Risk-based proof budget

Apply rigor according to risk:

- **High risk:** money/accounting, security or authority, canonical identity, time causality, provider historical evidence. Freeze exact invariants and run full acceptance.
- **Medium risk:** shared public seams and cross-package composition. Use focused contracts plus boundary validation.
- **Low risk:** local pure composition or formatting. Prefer one focused test and avoid speculative goldens.

Validation pyramid:

```text
edit loop             focused RED/GREEN test
Gate GREEN            Gate tests + direct boundaries
implementation commit frozen acceptance + one full suite
PASSED record         document/hash/repository checks only
release fan-in        full suite + cross-Gate parity
```

Do not repeatedly run the same expensive suite at every documentation transition unless a frozen policy explicitly requires it.

## Acceptance discipline

Freeze behavior before implementation:

- caller inputs;
- guaranteed outputs;
- invariants and ordering;
- structured failure precedence;
- explicit exclusions;
- the smallest runnable evidence that catches regression.

Freeze implementation type names only when another Gate must consume them. Avoid turning untested design guesses into policy.

Use exactly the required immutable commits: readiness freeze, implementation, and PASSED record. Add intermediate commits only for a real recovery boundary.

## Migration for this repository

The existing aggregate files remain authoritative until their active sections are migrated:

- `docs/implementation/target-driven-bar-v1-plan.md`
- `docs/implementation/acceptance-matrix.md`

Do not rewrite completed history merely for structure. Migrate active G11 and G12 plans first. During migration:

1. keep the current Acceptance Matrix registry as the sole status authority;
2. move one active Gate specification at a time;
3. replace moved prose with a stable link;
4. verify dependency links and acceptance commands;
5. introduce a separate registry only in one atomic migration that removes duplicate status ownership.

## Completion checklist

A decomposition is complete when:

- every active requirement belongs to one Gate or shared invariant file;
- every Gate has a useful vertical output;
- contract, evidence, and write-conflict dependencies are explicit;
- the DAG has no cycles;
- fan-out branches and fan-in Gate are visible;
- status has one source of truth;
- independent work can start without editing the same public seam;
- validation cost is proportional to risk;
- old aggregate prose links to the new authority instead of duplicating it.
