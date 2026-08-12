# G12A SourceSnapshot Contract Research

## Scope

G12A freezes caller-supplied raw source members into one deterministic, content-addressed, in-memory source snapshot. It records acquisition provenance separately from content identity, validates caller-declared source hashes, supports deterministic verification/member access, and fails atomically before G12B normalization.

G12A is not a network adapter, file scanner, repository, publisher, normalizer, retention system, or legal/completeness qualification.

## Primary authorities

1. [`tools/migration/legacy_migration/snapshots.py`](../../tools/migration/legacy_migration/snapshots.py), completed G00/WP-00C:
   - canonical snapshot bytes are a deterministic gzip-compressed USTAR archive;
   - member identity includes logical path, normalized mode, and exact bytes;
   - members are sorted; tar mtime/uid/gid are zero; uname/gname and gzip filename are empty; gzip mtime is zero and compression level is 9;
   - snapshot identity is the SHA-256 of exact archive bytes;
   - content-tree evidence records each member path/hash/size/mode.
2. [`tests/parity/test_source_snapshots.py`](../../tests/parity/test_source_snapshots.py):
   - repeated capture produces byte-identical archive output;
   - unsafe/nonregular members and path escapes fail closed;
   - tampering and archive-member attacks are detected;
   - committed legacy snapshots prove the deterministic recipe is stable.
3. [`docs/architecture/backtest-system-design.md`](../architecture/backtest-system-design.md), G12 and failure-closure rules:
   - Builder owns write-side source capture; Runtime remains offline/read-only;
   - acquisition failure or source hash mismatch cannot enter normalization;
   - immutable source provenance is required but does not itself prove coverage, retention, or decision grade.
4. [`architecture/import-boundaries.toml`](../../architecture/import-boundaries.toml):
   - `market-bundle-builder` currently depends only on `crypto_quant_market_data`;
   - Runtime must not import Builder;
   - G12A should remain stdlib-only and not introduce a hidden Domain dependency.

## Rejected one-blob seam

A single `source_hash = sha256(raw_bytes)` is insufficient because G00 already established that logical member key and normalized mode are identity-significant. It also cannot represent a finite multi-member vendor extract atomically. G12A therefore reuses the proven deterministic archive identity rather than inventing a second source-snapshot algorithm.

## Minimal contract

### RawSourceMember

One caller-supplied acquisition result:

- `member_key: str`;
- `raw_bytes: bytes | None` (`b""` is valid; `None` means acquisition incomplete);
- `mode: str`, exact `0644` or `0755`;
- `acquired_at_epoch_nanoseconds: int`, non-bool;
- optional exact `declared_sha256`.

G12A does not acquire bytes or read a path. The complete iterable is materialized once before validation/derivation, so a later failed member cannot leak a partial snapshot.

### Member-key policy

V1 accepts a deliberately narrow portable USTAR logical key:

- ASCII, 1–100 bytes;
- slash-separated segments;
- each segment matches `[A-Za-z0-9_][A-Za-z0-9._-]*`;
- no absolute path, empty/`.`/`..` segment, repeated/trailing slash, backslash, NUL, non-ASCII, leading dot, PAX extension, or overlong key.

If a real source needs a broader policy, the contract must be re-frozen rather than relying on implementation-specific `tarfile` behavior.

### SourceSnapshotProvenance

Immutable metadata only:

- `vendor_key`;
- `source_key`;
- `license_ref`;
- `retention_policy_ref`.

Each is a canonical lowercase stable key matching `[a-z][a-z0-9._-]*`. These are references, not credentials, URLs, headers, paths, mutable handles, legal conclusions, or retention proof.

### SourceSnapshotMember

Canonical evidence for one captured member:

- member key;
- content hash;
- byte count;
- normalized mode;
- acquisition epoch nanoseconds;
- optional declared source hash.

Members are sorted by member key and unique.

### SourceSnapshot

Successful immutable value:

- `snapshot_id = sha256:<digest of exact deterministic archive bytes>`;
- archive bytes, hidden from repr and excluded from canonical manifest;
- content-tree hash;
- canonical members;
- provenance;
- provenance hash;
- fixed development/deployment flags false.

`SourceSnapshot.to_canonical_dict()` is the source manifest value. No persisted path, URI, CAS key, repository handle, retention proof, artifact envelope, or manifest identity is added in G12A.

`member_bytes(member_key)` is the only downstream raw-member access. It verifies/decompresses in memory and returns exact bytes, including `b""`; invalid/unverified/missing access raises one fixed non-revealing error. G12B must not independently parse a tar archive.

### Content identity

Exact archive recipe matches G00:

- sorted regular USTAR members;
- name = logical member key;
- exact raw bytes;
- mode = 0644/0755;
- mtime/uid/gid = 0;
- uname/gname = empty;
- gzip filename = empty;
- gzip mtime = 0;
- gzip compression level = 9.

Member key, mode, and bytes affect `snapshot_id`. Input order, acquisition time, provenance, local paths, machine, process, and current time do not.

Content-tree preimage:

```text
{
  type: source_snapshot_content_tree,
  schema_version: 1,
  members: [{member_key, content_hash, byte_count, mode}, ...]
}
```

The content-tree hash is integrity evidence, not a second durable identity.

### Provenance identity

Provenance changes must not rewrite content identity. The provenance preimage binds:

```text
{
  type: source_snapshot_provenance,
  schema_version: 1,
  snapshot_id,
  vendor_key,
  source_key,
  license_ref,
  retention_policy_ref,
  members: [{member_key, acquired_at_epoch_nanoseconds, declared_sha256}, ...]
}
```

Thus identical archive content has one `snapshot_id`; acquisition/source/license/retention evidence has a separate `provenance_hash`.

### Canonical serialization

Builder cannot directly import Trading Domain canonical helpers under the frozen package DAG. G12A uses one private restricted stdlib encoder matching the repository canonical JSON grammar needed by this seam: UTF-8, compact separators, Unicode-key sorting, NFC strings, and only null/bool/non-bool integer/string/list/string-key mapping. Float/Decimal/datetime/bytes/set/non-string keys/cycles fail closed. Public binary bytes never enter canonical JSON.

## Structured outcome

`freeze_source_snapshot()` and `verify_source_snapshot()` return an XOR outcome containing either a snapshot or a structured failure. This keeps acquisition/integrity failures out of exception-message and partial-value paths.

Freeze precedence:

1. invalid snapshot input;
2. unsafe member;
3. duplicate member;
4. acquisition failed;
5. declared source hash mismatch.

Verify precedence:

1. invalid snapshot input;
2. archive invalid;
3. snapshot ID mismatch;
4. content-tree/member evidence mismatch;
5. provenance hash mismatch.

Constructors reject malformed individual values with `TypeError`/`ValueError`; complete freeze/verify operations use the structured outcome. Failures expose stable codes and at most one independently safe member key, never bytes, URL/header/credential values, exception text, stack, local path, or current-time data.

Verification parses entirely in memory, rejects nonregular/unsafe/duplicate/unsorted/noncanonical tar metadata, reconstructs and byte-compares the exact canonical archive, then recomputes archive/member/content/provenance values.

## Atomicity

G12A atomicity means only value-level capture atomicity: either every supplied member is valid and one complete immutable snapshot is returned, or no snapshot is returned. Durable file/object-store publication, temporary files, concurrent deduplication, locks, repository retrieval, and retention belong to G12D.

## Package/API placement

Add one module:

- `crypto_quant_bundle_builder.source_snapshots`

Root exports:

- `RawSourceMember`;
- `SourceSnapshotProvenance`;
- `SourceSnapshotMember`;
- `SourceSnapshot`;
- `SourceSnapshotFailureCode`;
- `SourceSnapshotFailure`;
- `SourceSnapshotOutcome`;
- `freeze_source_snapshot`;
- `verify_source_snapshot`.

Ponytail decision: no speculative `SourceSnapshotRef`. G12B can consume `SourceSnapshot` directly in-process; G12D can add the smallest durable reference once repository publication exists.

## Explicit exclusions

- HTTP/file/database/cloud acquisition, provider SDK, auth, credentials, pagination, retry, or current endpoint state;
- filesystem scanning, symlink handling, source-root paths, CLI, registry, protocol, callback, plugin, cache, or current wall clock;
- normalization, parser mapping, canonical market records, Bundle manifest/validation, Reader, Runtime, Engine, or Runner;
- durable publication, CAS, URI/path identity, concurrent deduplication, encryption, retention or retrieval proof;
- source completeness, revision retention, license adjudication, data admissibility, decision grade, live, or deployment authorization.

## Fixture/readiness shape

A static synthetic fixture should contain three members, including one zero-byte member and one executable member. It freezes exact archive bytes, manifest/member/content/provenance values, hashes, reverse-input parity, provenance-only identity change, key/mode/byte sensitivity, safe member access, every failure code/precedence, later-member acquisition atomicity, archive tampering/noncanonical tar controls, restricted-canonical vectors, repeat parity, and false qualification flags.

Real/sensitive source payloads are not required or permitted for G12A acceptance.
