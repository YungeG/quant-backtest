# G12F Reader and Partition Parity Contract Research

## Decision status

G12F remains `DRAFT`. G12E now supplies two real adapters at the existing `MarketBundleReader` seam: `InMemoryMarketBundleReader` and `LocalMarketBundleReader`. G12F should compare those adapters without adding another Reader, Cursor, Runtime mode, or storage representation.

The old roadmap wording refers to Parquet/Arrow partitions and memory-map modes. That representation was explicitly deferred by G12E because G12D publishes only manifest-bound canonical JSON stream payloads. G12F therefore cannot claim Parquet, Arrow, memory-map, or physical-partition-mode parity. Its compatible v1 scope is exact logical stream, Timeline, Engine, and auditable execution parity over the same immutable Bundle identity.

## Reused authority

G12F must reuse without modifying:

- `MarketBundleReader`, `EventCursor`, `InMemoryMarketBundleReader`, and `LocalMarketBundleReader`;
- G12D publication identity and G12E all-or-nothing verification;
- `DeterministicTimeline`, whose source cursors are fixed to one event and whose output batch size is operational;
- `ResolvedExecutionCase`, whose canonical identity excludes `timeline_batch_size` but includes Timeline/Bundle semantics;
- `EngineExecutionResult.result_hash` and `ExecutionResultHasher`;
- G07 `AuditableBacktestRunner`, Attempt Evidence, Execution Hash, and canonical publication;
- Comparator Contract v1 for exact comparison and first-divergence reporting.

No new parity algorithm is needed. Comparator Contract v1 already provides exact and sequence rules and reports the first differing sequence index.

## Canonical comparison model

For one G12D publication, G12F constructs:

1. an in-memory Reader from the exact decoded public `MarketEvent` values;
2. a local persisted Reader opened from the exact Bundle ref;
3. identical Timeline windows and stream selections over each Reader;
4. identical execution-case semantics, varying only Reader adapter and operational batch sizes;
5. G07 attempts whose economic output is compared by canonical execution result hash.

The parity projection should contain ordered rows for:

- Bundle ref and Manifest hash;
- each stream key, manifest content hash, event count, Event IDs, and Event hashes;
- Timeline event IDs, Event hashes, segments, and terminal cursor hash;
- execution-case hash and identity-manifest hash;
- Engine result hash, Trace hash, Ledger state hash, Snapshot hash, and Run End report hash;
- G07 Attempt execution result hash and canonical Result identity.

Reader implementation class name, absolute repository root, Cursor batch size, Timeline batch size, temporary path, Attempt ID, and Evidence Manifest hash are operational or attempt evidence. They may be recorded separately but must not be compared as economic identity.

## Required parity axes

The minimum matrix is:

```text
Reader adapter:       in-memory | local persisted
Reader batch size:    1 | 2 | larger than stream
Timeline batch size:  1 | 2 | larger than output
Run path:             direct Engine | G07 auditable Runner
```

All cells for one semantic case must produce the same:

- Bundle/Manifest identity;
- per-stream Event ID/hash sequence;
- Timeline Event ID/hash/segment sequence;
- execution-case hash;
- Engine result/Trace/Ledger/Snapshot/Run End hashes;
- G07 execution result hash.

G07 Attempt and Evidence identities must remain distinct where the G07 contract requires distinct attempts. Equality is required for their bound execution result hash, not for Attempt ID or Evidence Manifest hash.

## Partition terminology

In G12F v1, a **logical partition** is one manifest-declared stream and its exact ordered canonical event tuple. The physical file `streams/<index>.payload` is G12D storage evidence, not a separately configurable partitioning strategy.

A future physical partition or columnar parity gate requires a preceding representation contract that freezes:

- representation manifest and hash;
- file/row-group partition keys and ordering;
- codec/compression/library versions where bytes depend on them;
- mapping from logical stream identity to physical partitions;
- atomic linkage to the existing Bundle ref.

Until then, G12F must reject claims about partition-layout alternatives or memory-map parity.

## First-divergence semantics

G12F should use Comparator Contract v1 sequence rules over stream and Timeline rows. A mismatch identifies at least:

- comparison layer;
- stream key;
- zero-based event position;
- expected and actual Event ID/hash.

For downstream execution mismatches, the report adds the first differing canonical execution layer available from the projection. It must not hide an earlier stream or Timeline mismatch behind a later aggregate result hash.

A passing G12F gate requires `MATCH`. Unlike G10H, G12F has no approved semantic changes, tolerance, or not-comparable rows: both sides consume the same Bundle authority through the same Reader Protocol.

## Failure and qualification semantics

G12F is pure offline parity tooling. It must fail closed for:

- Bundle ref or Manifest mismatch;
- missing, duplicated, reordered, or altered stream/Event evidence;
- Timeline sequence or segment mismatch;
- execution-case identity mismatch;
- Engine or G07 execution result mismatch;
- missing comparator classification or malformed parity projection;
- any claim of Parquet/Arrow, memory-map, decision-grade, live, or deployment authority.

G12F does not prove source completeness, future retention, deterministic rebuild, provider correctness, decision-grade eligibility, or deployment authorization. All qualification flags remain false.

## Minimal seam

G12F should add no production package export. The smallest implementation is parity tooling plus fixtures/tests:

```text
tools/parity/market_bundle_reader.py
tools/parity/run_market_bundle_reader_parity.py
tests/parity/contracts/market-bundle-reader-g12f-v1.json
tests/parity/fixtures/market-bundle-reader-g12f-v1/
```

The tool consumes already-produced canonical projections or a test-owned synthetic case. It must not import Builder, Runtime Engine, Runner, or MarketBundle Reader production modules. Tests/support code owns generating the in-memory, persisted, Timeline, Engine, and G07 projections before invoking the isolated comparator.

This preserves the existing parity seam: production systems generate authoritative artifacts; offline parity tooling only validates frozen canonical projections.

## Architecture constraints

- owner is repository-root parity tooling;
- no new public root export or package dependency;
- production Runtime, Market Data, Builder, and Kernel remain G12F-branchless;
- parity tool imports only stdlib and existing `legacy_migration.parity` helpers;
- no network, provider SDK, database, subprocess, dynamic import, wall clock, cache, or mutable global state;
- no Parquet, Arrow, Pandas, DataFrame, memory map, or sidecar generation;
- no global epsilon, tolerance, or `approved_change` rule.

## Fixture plan

Fixture ID: `market-bundle-reader-g12f-v1`.

Freeze:

- one published multi-stream synthetic Bundle;
- exact in-memory/local stream Event ID/hash parity for Reader batch sizes `1`, `2`, and larger than each stream;
- exact Timeline sequence/segment/cursor parity for Timeline batch sizes `1`, `2`, and larger than output;
- identical execution-case, Engine result, Trace, Ledger, Snapshot, and Run End hashes;
- two G07 attempts with distinct Attempt/Evidence identities and equal execution result hash;
- first divergence for stream event mutation, reordering, omission, Timeline segment mutation, and execution result mutation;
- malformed/unclassified projection fail-closed;
- repeat/root-independent report bytes;
- `decision_grade_eligible=false` and `deployment_authorized=false`.

## Product decision before freeze

Freeze G12F as logical Reader/Timeline/Execution parity over the representation G12D/G12E actually own. If physical Parquet/Arrow partition or memory-map parity is still required, insert a separately hashed representation gate before extending G12F; do not reopen G12C–E or add an unhashed sidecar.
