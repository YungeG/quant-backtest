# G12E Persisted MarketBundle Reader Contract Research

## Decision status

G12E remains `DRAFT`. The current repository contracts expose a real boundary conflict that must be resolved before freeze.

G12D publishes the exact opaque stream payload bytes whose SHA-256 equals each `MarketStreamManifest.content_hash`. For the first frozen G12C fixture those bytes are `canonical_bytes(tuple(events_for_stream))`. The final repository layout therefore contains canonical JSON event tuples in `streams/<index>.payload`; it does not contain Parquet or Arrow data.

The existing G12E roadmap text instead says that G12E owns Parquet/Arrow columnar storage, memory mapping, and a bounded Reader adapter. A Reader-only gate cannot transform the G12D payload into Parquet while preserving the existing stream content hash, and no frozen manifest field identifies or hashes a second columnar representation.

## Reused authority

G12E must reuse without modifying:

- `MarketBundleReader`;
- `EventCursor`;
- `MarketBundleManifest` and `MarketBundleRef`;
- `MarketStreamManifest`;
- `MarketEvent`;
- `InputValidationFailure` and its existing issue codes;
- `MarketBundleIntegrityError` and `MarketBundleStreamError`;
- G12D final paths, canonical manifest/publication/retention files, and exact current-retrievability verification.

WP-06A already freezes cursor identity, bounded batch behavior, requirement validation, cross-bundle/cross-stream resume rejection, canonical event ordering, and page-size parity. G12E should implement that Protocol rather than create a second cursor or reader abstraction.

## Proven persisted representation

The only representation currently published and cryptographically bound by G12C/G12D is:

```text
bundles/<bundle-key>/<manifest-digest>/
  manifest.json
  streams/000.payload
  streams/001.payload
  ...
  publication.json
  retention-proof.json
```

For each stream:

```text
sha256(stream payload bytes) == MarketStreamManifest.content_hash
```

For the current grammar:

```text
stream payload bytes == canonical_bytes(tuple(events_for_stream))
```

G12D treats those bytes as opaque. It neither declares a codec field nor owns a columnar transformation.

## Conflict with the current roadmap wording

A Parquet file cannot normally have the same bytes or SHA-256 as the canonical JSON tuple that G12C hashes. Consequently, one of the following must change before a columnar reader can be frozen:

1. the G12E outcome becomes a concrete persisted-canonical-payload reader;
2. a new Builder gate produces and manifests a separately hashed columnar representation before the Reader gate;
3. G12C/G12D identity and publication contracts are reopened to make the published stream payload itself columnar.

An unhashed or identity-external Parquet sidecar is rejected. It would let the Reader serve bytes that are not committed by `MarketBundleManifest`, weakening the fail-closed content-addressed boundary.

## Minimal compatible G12E seam

If G12E is narrowed to the representation that G12D actually publishes, the smallest seam is one concrete class in `market-data-contracts`:

```python
LocalMarketBundleReader.open(
    *,
    repository_root: Path,
    bundle_ref: MarketBundleRef,
) -> LocalMarketBundleReader
```

The resulting object implements the existing `MarketBundleReader` Protocol and exposes only its existing operations:

- `bundle_ref`;
- `manifest`;
- `validate_requirements(...)`;
- `open_cursor(...)`;
- `read_batch(...)`;
- `resume_cursor(...)`.

The absolute root is operational input only. It never enters identity, cursor evidence, failures, or canonical output. No generic repository Protocol, URI, callback, registry, Reader factory, or codec plugin is needed.

## Open and verification order

A compatible local Reader should fail closed before serving any event:

1. validate exact absolute `Path` root and exact `MarketBundleRef`;
2. derive the G12D final directory from Bundle identity;
3. reject missing paths, symlinks, writable publication trees, and any extra/missing final entries;
4. load canonical `manifest.json` and require `MarketBundleRef.from_manifest(manifest) == bundle_ref`;
5. load and verify exact canonical `publication.json` and `retention-proof.json` linkage;
6. verify every declared stream path and payload SHA-256 before decoding;
7. decode the frozen canonical event tuple representation;
8. reconstruct exact `MarketEvent` values and apply all WP-06A stream-set, count, declaration, uniqueness, coverage, ordering, and content-hash checks;
9. only then expose cursor operations.

No partially verified stream may be read.

## Failure semantics

Open-time repository, canonical JSON, path-cover, hash, manifest, event-envelope, or ordering failures should raise `MarketBundleIntegrityError`. Cursor misuse continues to raise `MarketBundleStreamError`. Unknown requested streams and missing capabilities continue to return `InputValidationFailure` through the existing Protocol methods.

Failures must not expose absolute paths, raw payloads, exception text, hostname, PID, or wall-clock data. G12E does not map failures to Runtime outcomes.

## Ordering and visibility

G12E adds no new visibility policy. It returns the exact canonical stream sequence already committed by G12C:

```text
(available_time.epoch_nanoseconds, phase.rank, phase.code, source_sequence.value)
```

Batch size and cursor resume must not alter event ID/hash sequence. Event-time coverage and availability causality remain WP-06A/G12C authority.

## Columnar alternatives

### Option A — narrow G12E to the persisted canonical payload reader

- compatible with all PASSED G12C/G12D identities;
- no new dependency;
- directly unlocks a persisted-vs-in-memory parity gate;
- defers Parquet/Arrow packaging until a manifest-owned representation contract exists.

This is the recommended minimal path.

### Option B — insert a columnar packaging gate before G12E

A new Builder-owned gate would define:

- one exact Parquet or Arrow IPC version;
- schema and logical-to-physical field mapping;
- compression and encoding settings;
- partition and file naming;
- separately hashed representation manifest;
- atomic publication linkage to the logical Bundle ref;
- toolchain/library version identity where it affects bytes.

G12E would then read that newly frozen representation. This preserves the roadmap's columnar objective but adds a required contract and dependency.

### Option C — reopen G12C/G12D

G12C stream content hashes and G12D payload publication would be changed so the authoritative payload is columnar. This invalidates or supersedes PASSED contracts and fixtures and is not recommended without an explicit migration decision.

## Rejected approach

Do not generate or accept an unmanifested Parquet/Arrow sidecar next to the G12D final directory. G12D final path exact-cover verification would reject it, and storing it elsewhere would leave its content outside Bundle identity and current-retention proof.

## Fixture plan for Option A

Fixture ID: `local-market-bundle-reader-v1`.

Freeze:

- exact G12D first fixture open;
- manifest/ref/publication/retention linkage verification;
- one-stream and multi-stream reads;
- batch sizes `1`, `2`, and larger than stream length;
- exhausted cursor behavior;
- cross-bundle and cross-stream resume rejection;
- unknown stream and missing capability results;
- missing/extra/tampered/symlink/writable final entries;
- malformed canonical JSON and malformed MarketEvent envelopes;
- stream count/hash/order mismatch;
- path/hash/event-sequence repeat parity;
- no absolute-root or clock leakage.

G12F can then compare `InMemoryMarketBundleReader` with this persisted reader exactly.

## Architecture constraints

- owner remains `market-data-contracts`;
- no import from `market-bundle-builder`, Runtime, Trading Kernel, source adapters, network, database, Pandas, or vendor SDKs;
- cross-package imports use public roots;
- no wall clock, global mutable cache, lazy partial verification, or deployment/decision-grade claims;
- no DataFrame exposure;
- no new generic Reader/Repository Protocol.

## Product decision required before freeze

Choose whether G12E is:

1. the minimal G12D-compatible local canonical-payload Reader; or
2. still a Parquet/Arrow Reader, in which case a new columnar packaging/manifest gate must precede it.

Reopening PASSED G12C/G12D is a third, high-cost option and is not recommended.
